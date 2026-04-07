import logging
import os
import time
import uuid
import concurrent.futures
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import requests
from airflow.models import Variable
from airflow.providers.amazon.aws.hooks.s3 import S3Hook
from airflow.providers.postgres.hooks.postgres import PostgresHook

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
###
API_KEY               = Variable.get("LASTFM_API_KEY")
BASE_URL              = "http://ws.audioscrobbler.com/2.0/"
S3_BUCKET             = Variable.get("S3_BUCKET_NAME")
AWS_ACCESS_KEY_ID     = Variable.get("S3_ACCESS_KEY")
AWS_SECRET_ACCESS_KEY = Variable.get("S3_SECRET_KEY")
LAST_PAGE_KEY         = "LAST_PAGE"

COLUMNS = [
    "artist", "title",
    "play_cnt", "listener_cnt",
    "tag1", "tag2", "tag3", "tag4", "tag5"
]

def extract_tracks(**kwargs):
    logging.info("Start extract_tracks")
    tracks = []
    limit = 50
    start_page = int(Variable.get(LAST_PAGE_KEY, default_var=1))
    end_page = start_page + 2

    for page in range(start_page, end_page + 1):
        params = {
            "method": "chart.getTopTracks",
            "api_key": API_KEY,
            "format": "json",
            "limit": limit,
            "page": page
        }
        resp = requests.get(BASE_URL, params=params)
        for t in resp.json().get('tracks', {}).get('track', []):
            tracks.append((t['artist']['name'], t['name']))
        time.sleep(0.2)

    next_page = end_page + 1 if end_page + 1 <= 200 else 1
    Variable.set(LAST_PAGE_KEY, next_page)
    kwargs['ti'].xcom_push(key='tracks', value=tracks)
    logging.info(f"Extracted {len(tracks)} tracks. Next page: {next_page}")


def _fetch_track_info(artist: str, title: str) -> tuple:
    """단일 트랙 정보 조회 — ThreadPoolExecutor 워커에서 호출"""
    params = {
        "method": "track.getInfo",
        "artist": artist,
        "track": title,
        "api_key": API_KEY,
        "format": "json"
    }
    resp = requests.get(BASE_URL, params=params, timeout=10)
    info = resp.json().get('track', {})
    tags = [tag['name'] for tag in info.get('toptags', {}).get('tag', [])][:5]
    tags += [None] * (5 - len(tags))
    playcount = int(info.get('playcount', 0))
    listeners = int(info.get('listeners', 0))
    return (artist, title, playcount, listeners, *tags)


def enrich_with_tags(**kwargs):
    """
    [BEFORE] 직렬 처리: 150트랙 × (API ~0.3s + sleep 0.2s) ≒ 75s
    [AFTER]  병렬 처리: ThreadPoolExecutor(max_workers=10) → ~8s
    """
    logging.info("Start enrich_with_tags (parallel)")
    ti = kwargs['ti']
    tracks = ti.xcom_pull(key='tracks')
    pg_hook = PostgresHook(postgres_conn_id='redshift_conn')

    enriched = [None] * len(tracks)
    error_records = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        future_to_idx = {
            executor.submit(_fetch_track_info, artist, title): idx
            for idx, (artist, title) in enumerate(tracks)
        }
        for future in concurrent.futures.as_completed(future_to_idx):
            idx = future_to_idx[future]
            artist, title = tracks[idx]
            try:
                enriched[idx] = future.result()
            except Exception as e:
                logging.warning(f"Error for {artist}-{title}: {e}")
                error_records.append((artist, title, "fetch_error"))
                enriched[idx] = (artist, title, 0, 0, None, None, None, None, None)

    # 에러 레코드 일괄 적재 (개별 INSERT 대신 executemany로 최적화)
    if error_records:
        pg_hook.run(
            """
            INSERT INTO raw_data.track_out (artist, title, reason, dropped_at)
            VALUES (%s, %s, %s, current_timestamp);
            """,
            parameters=error_records
        )

    ti.xcom_push(key='enriched_tracks', value=enriched)
    logging.info(f"Enriched {len(enriched)} tracks ({len(error_records)} errors)")


def save_to_s3_parquet(**kwargs):
    logging.info("Start save_to_s3_parquet")
    ti = kwargs['ti']
    enriched = ti.xcom_pull(key='enriched_tracks')
    df = pd.DataFrame(enriched, columns=COLUMNS)

    now_kst = datetime.now(ZoneInfo("Asia/Seoul"))
    filename = f"track_data_{now_kst:%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:8]}.parquet"
    local_path = f"/tmp/{filename}"

    df.to_parquet(local_path, engine="pyarrow", index=False, compression="snappy")

    s3_key = f"track_data/{filename}"
    S3Hook(aws_conn_id='aws_s3_conn').load_file(
        filename=local_path,
        key=s3_key,
        bucket_name=S3_BUCKET,
        replace=True
    )

    ti.xcom_push(key='s3_key', value=s3_key)
    os.remove(local_path)
    logging.info(f"Uploaded to S3: {s3_key}")


def copy_to_redshift(**kwargs):
    """
    [BEFORE] TRUNCATE → COPY 순차 실행. COPY 실패 시 raw_data.track_data가 빈 상태로 남음.
             하위 UPDATE/INSERT도 0건 처리되어 analytics_data.top_tag5가 갱신되지 않음.

    [AFTER]  Staging 테이블 패턴으로 원자성 보장:
             1) raw_data.track_data_staging에 COPY
             2) 성공 시 트랜잭션 내에서 track_data ← staging 교체 + analytics 갱신
             3) 어느 단계에서든 실패 시 ROLLBACK → 기존 데이터 보존
    """
    logging.info("Start copy_to_redshift (transactional staging pattern)")
    ti = kwargs['ti']
    s3_key = ti.xcom_pull(key='s3_key')
    col_str = ", ".join(COLUMNS)

    hook = PostgresHook(postgres_conn_id='redshift_conn')
    conn = hook.get_conn()
    conn.autocommit = False  # 트랜잭션 수동 관리

    try:
        cur = conn.cursor()

        # Step 1: staging 테이블에 COPY (기존 track_data 미변경)
        cur.execute("TRUNCATE TABLE raw_data.track_data_staging;")
        cur.execute(f"""
            COPY raw_data.track_data_staging ({col_str})
            FROM 's3://{S3_BUCKET}/{s3_key}'
            ACCESS_KEY_ID '{AWS_ACCESS_KEY_ID}'
            SECRET_ACCESS_KEY '{AWS_SECRET_ACCESS_KEY}'
            FORMAT AS PARQUET;
        """)
        logging.info("COPY to staging complete")

        # Step 2: staging → track_data 교체 (트랜잭션 내)
        cur.execute("TRUNCATE TABLE raw_data.track_data;")
        cur.execute(f"""
            INSERT INTO raw_data.track_data ({col_str})
            SELECT {col_str} FROM raw_data.track_data_staging;
        """)

        # Step 3: analytics_data.top_tag5 UPDATE (변경된 행만)
        cur.execute("""
            UPDATE analytics_data.top_tag5 AS tgt
            SET play_cnt = src.play_cnt,
                listener_cnt = src.listener_cnt,
                tag1 = src.tag1,
                tag2 = src.tag2,
                tag3 = src.tag3,
                tag4 = src.tag4,
                tag5 = src.tag5,
                load_time = GETDATE() AT TIME ZONE 'Asia/Seoul'
            FROM raw_data.track_data AS src
            WHERE tgt.artist = src.artist
              AND tgt.title = src.title
              AND (tgt.play_cnt <> src.play_cnt OR tgt.listener_cnt <> src.listener_cnt);
        """)

        # Step 4: analytics_data.top_tag5 INSERT (신규 유효 행)
        cur.execute("""
            INSERT INTO analytics_data.top_tag5 (
                artist, title, play_cnt, listener_cnt,
                tag1, tag2, tag3, tag4, tag5, load_time
            )
            SELECT src.artist, src.title, src.play_cnt, src.listener_cnt,
                   src.tag1, src.tag2, src.tag3, src.tag4, src.tag5,
                   GETDATE() AT TIME ZONE 'Asia/Seoul'
            FROM raw_data.track_data AS src
            LEFT JOIN analytics_data.top_tag5 AS tgt
              ON src.artist = tgt.artist AND src.title = tgt.title
            WHERE tgt.artist IS NULL
              AND src.artist IS NOT NULL AND src.artist <> ''
              AND src.title IS NOT NULL AND src.title <> ''
              AND src.play_cnt >= 0
              AND src.listener_cnt >= 0
              AND NOT (src.tag1 IS NULL AND src.tag2 IS NULL AND src.tag3 IS NULL
                       AND src.tag4 IS NULL AND src.tag5 IS NULL);
        """)

        # Step 5: bad_records 적재
        cur.execute("""
            INSERT INTO raw_data.bad_records_top_tag5 (
                artist, title, play_cnt, listener_cnt,
                tag1, tag2, tag3, tag4, tag5,
                error_reason, load_time
            )
            SELECT artist, title, play_cnt, listener_cnt,
                   tag1, tag2, tag3, tag4, tag5,
                   CASE
                       WHEN artist IS NULL OR artist = '' THEN 'invalid artist'
                       WHEN title IS NULL OR title = '' THEN 'invalid title'
                       WHEN play_cnt < 0 THEN 'negative play_cnt'
                       WHEN listener_cnt < 0 THEN 'negative listener_cnt'
                       WHEN tag1 IS NULL AND tag2 IS NULL AND tag3 IS NULL
                            AND tag4 IS NULL AND tag5 IS NULL THEN 'no tags'
                       ELSE 'unknown'
                   END AS error_reason,
                   GETDATE() AT TIME ZONE 'Asia/Seoul'
            FROM raw_data.track_data
            WHERE artist IS NULL OR artist = ''
               OR title IS NULL OR title = ''
               OR play_cnt < 0
               OR listener_cnt < 0
               OR (tag1 IS NULL AND tag2 IS NULL AND tag3 IS NULL
                   AND tag4 IS NULL AND tag5 IS NULL);
        """)

        conn.commit()
        logging.info("copy_to_redshift committed successfully (staging pattern)")

    except Exception as e:
        conn.rollback()
        logging.error(f"copy_to_redshift failed, rolled back: {e}")
        raise
    finally:
        cur.close()
        conn.close()
