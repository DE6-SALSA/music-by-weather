import pandas as pd
import requests
import re
import logging
import os
import concurrent.futures

from zoneinfo import ZoneInfo
from datetime import datetime, timedelta
from urllib.parse import urlencode
from airflow.providers.amazon.aws.hooks.s3 import S3Hook
from airflow.providers.postgres.hooks.postgres import PostgresHook

TEMP_PATH = "/opt/airflow/data/weather_data.csv"

def weather_condition(pty, t1h, wsd, sky):
    if pty in [3, 7]:
        return 'Snowy'
    if pty in [1, 2, 4, 5] and wsd > 7:
        return 'Stormy'
    if pty in [1, 2, 4, 5]:
        return 'Rainy'
    if t1h <= 5:
        return 'Cold'
    if t1h >= 28:
        return 'Hot'
    if wsd > 6:
        return 'Windy'
    if sky in [3, 4]:
        return 'Cloudy'
    return 'Clear'

def _fetch_single_region(row_data: dict, service_key: str, base_date: str, base_time: str) -> dict | None:
    """단일 지역 날씨 조회 — ThreadPoolExecutor 워커에서 호출"""
    level1 = row_data['level1']
    level2 = row_data['level2']
    nx, ny = row_data['nx'], row_data['ny']

    params = {
        "authKey": service_key,
        "numOfRows": 100,
        "pageNo": 1,
        "dataType": "JSON",
        "base_date": base_date,
        "base_time": base_time,
        "nx": nx,
        "ny": ny
    }
    url = "https://apihub.kma.go.kr/api/typ02/openApi/VilageFcstInfoService_2.0/getUltraSrtFcst?" + urlencode(params, safe="=")

    try:
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        items = res.json()['response']['body']['items']['item']

        data = {}
        for item in items:
            cat = item['category']
            val = item['fcstValue']
            if cat == "RN1":
                if val in ["강수없음", "1mm 미만"]:
                    val = "0"
                else:
                    val = re.sub(r"[^0-9.]", "", val)
            data[cat] = val

        return {
            "LEVEL1": level1,
            "LEVEL2": level2,
            "DATE": datetime.strptime(base_date, "%Y%m%d").strftime("%Y-%m-%d"),
            "TIME": base_time,
            "PTY": int(data.get("PTY", -1)),
            "REH": int(data.get("REH", -1)),
            "RN1": float(data.get("RN1", -1)),
            "T1H": float(data.get("T1H", -1)),
            "WSD": float(data.get("WSD", -1)),
            "SKY": int(data.get("SKY", -1)),
        }
    except Exception as e:
        logging.warning(f"❌ {level1}_{level2} failed: {e}")
        return None


def fetch_weather_data(csv_path: str, service_key: str, **kwargs):
    """
    [BEFORE] 직렬 처리: ~250개 지역 × 0.5s ≒ 125s
    [AFTER]  병렬 처리: ThreadPoolExecutor(max_workers=20) → ~8s
    """
    def get_base_datetime():
        now = datetime.now(ZoneInfo("Asia/Seoul"))
        if now.minute < 45:
            now -= timedelta(hours=1)
        return now.strftime("%Y%m%d"), now.strftime("%H") + "30"

    df = pd.read_csv(csv_path)
    base_date, base_time = get_base_datetime()
    logging.info(f"Fetching weather data (parallel) | base: {base_date} {base_time}")

    # DataFrame rows를 dict 리스트로 변환
    rows = [
        {
            "level1": str(r["level1"]),
            "level2": str(r["level2"]) if pd.notnull(r["level2"]) else "",
            "nx": int(r["nx"]),
            "ny": int(r["ny"]),
        }
        for _, r in df.iterrows()
    ]

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        futures = {
            executor.submit(_fetch_single_region, row, service_key, base_date, base_time): row
            for row in rows
        }
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            if result is not None:
                results.append(result)

    logging.info(f"Fetched {len(results)}/{len(rows)} regions successfully")

    weather_df = pd.DataFrame(results)
    weather_df['weather_condition'] = weather_df.apply(
        lambda row: weather_condition(row['PTY'], row['T1H'], row['WSD'], row['SKY']),
        axis=1
    )

    weather_df.to_csv(TEMP_PATH, index=False)
    logging.info(f"weather data saved: {TEMP_PATH}")

    kwargs['ti'].xcom_push(key='base_date', value=base_date)
    kwargs['ti'].xcom_push(key='base_time', value=base_time)

def upload_to_s3(bucket_name: str, aws_conn_id: str, **kwargs):
    ti = kwargs['ti']
    base_date = ti.xcom_pull(key='base_date', task_ids='fetch_weather_data')
    base_time = ti.xcom_pull(key='base_time', task_ids='fetch_weather_data')

    filename = f'weather_data_{base_date}_{base_time}.csv'
    s3_key = f'weather_data/{filename}'

    hook = S3Hook(aws_conn_id=aws_conn_id)
    hook.load_file(
        filename=TEMP_PATH,
        key=s3_key,
        bucket_name=bucket_name,
        replace=True
    )
    logging.info(f"s3 upload complete: s3://{bucket_name}/{s3_key}")
    ti.xcom_push(key='s3_key', value=s3_key)

def copy_to_redshift(redshift_conn_id: str, table_name: str, s3_bucket: str, aws_access_key_id: str, aws_secret_access_key: str, **kwargs):
    redshift = PostgresHook(postgres_conn_id=redshift_conn_id)

    s3_key = kwargs['ti'].xcom_pull(key='s3_key', task_ids='upload_to_s3')
    s3_path = f's3://{s3_bucket}/{s3_key}'

    copy_sql = f"""
        COPY {table_name}
        FROM '{s3_path}'
        ACCESS_KEY_ID '{aws_access_key_id}'
        SECRET_ACCESS_KEY '{aws_secret_access_key}'
        CSV
        IGNOREHEADER 1
        REGION 'ap-northeast-2';
    """

    redshift.run(copy_sql)
    logging.info(f"Redshift COPY complete: {table_name}")
