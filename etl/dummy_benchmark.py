import os
import uuid
import time
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from datetime import datetime
from zoneinfo import ZoneInfo
from airflow.models import Variable
from airflow.providers.amazon.aws.hooks.s3 import S3Hook
from airflow.providers.postgres.hooks.postgres import PostgresHook

S3_BUCKET = Variable.get("S3_BUCKET_NAME")
AWS_ACCESS_KEY_ID = Variable.get("S3_ACCESS_KEY")
AWS_SECRET_ACCESS_KEY = Variable.get("S3_SECRET_KEY")

COLUMNS = [
    "artist", "title", "play_cnt", "listener_cnt",
    "tag1", "tag2", "tag3", "tag4", "tag5", "load_time"
]

def generate_dummy_csv_parquet(size_mb: int, **kwargs):
    rows = (size_mb * 1024 * 1024) // 150
    now = datetime.now(ZoneInfo("Asia/Seoul")).replace(tzinfo=None)

    df = pd.DataFrame({
        "artist": ["dummy_artist"] * rows,
        "title": ["dummy_title"] * rows,
        "play_cnt": [123] * rows,
        "listener_cnt": [45] * rows,
        "tag1": ["rock"] * rows,
        "tag2": ["pop"] * rows,
        "tag3": ["jazz"] * rows,
        "tag4": ["metal"] * rows,
        "tag5": ["folk"] * rows,
        "load_time": [now] * rows,
    })
    
    df["play_cnt"] = df["play_cnt"].astype("int32")
    df["listener_cnt"] = df["listener_cnt"].astype("int32")
    df["load_time"] = pd.to_datetime(df["load_time"]).dt.tz_localize(None)

    filename_base = f"track_data_{now:%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:6]}"
    csv_path = f"/tmp/{filename_base}.csv"
    parquet_path = f"/tmp/{filename_base}.parquet"

    df.to_csv(csv_path, index=False)
    pq.write_table(pa.Table.from_pandas(df), parquet_path, compression='snappy')

    ti = kwargs['ti']
    ti.xcom_push(key=f'{size_mb}_csv_file', value=csv_path)
    ti.xcom_push(key=f'{size_mb}_parquet_file', value=parquet_path)
    ti.xcom_push(key=f'{size_mb}_row_count', value=len(df))



def upload_to_s3(size_mb: int, **kwargs):
    ti = kwargs['ti']
    csv_path = ti.xcom_pull(key=f'{size_mb}_csv_file')
    parquet_path = ti.xcom_pull(key=f'{size_mb}_parquet_file')

    now = datetime.now(ZoneInfo("Asia/Seoul"))
    base = f"track_data_{now:%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:6]}"
    csv_key = f"benchmark/csv/{base}.csv"
    parquet_key = f"benchmark/parquet/{base}.parquet"

    s3 = S3Hook(aws_conn_id='aws_s3_conn')
    s3.load_file(csv_path, bucket_name=S3_BUCKET, key=csv_key, replace=True)
    s3.load_file(parquet_path, bucket_name=S3_BUCKET, key=parquet_key, replace=True)

    ti.xcom_push(key=f'{size_mb}_csv_key', value=csv_key)
    ti.xcom_push(key=f'{size_mb}_parquet_key', value=parquet_key)
    ti.xcom_push(key=f'{size_mb}_csv_size', value=os.path.getsize(csv_path) / 1024**2)
    ti.xcom_push(key=f'{size_mb}_parquet_size', value=os.path.getsize(parquet_path) / 1024**2)

    os.remove(csv_path)
    os.remove(parquet_path)

def copy_to_redshift(size_mb: int, **kwargs):
    ti = kwargs['ti']
    csv_key = ti.xcom_pull(key=f'{size_mb}_csv_key')
    parquet_key = ti.xcom_pull(key=f'{size_mb}_parquet_key')

    print(f"[DEBUG] size_mb: {size_mb}")
    print(f"[DEBUG] CSV key: {csv_key}")
    print(f"[DEBUG] Parquet key: {parquet_key}")
    
    pg = PostgresHook(postgres_conn_id='redshift_conn')

    csv_sql = f"""
        COPY raw_data.data_csv ({', '.join(COLUMNS)})
        FROM 's3://{S3_BUCKET}/{csv_key}'
        ACCESS_KEY_ID '{AWS_ACCESS_KEY_ID}'
        SECRET_ACCESS_KEY '{AWS_SECRET_ACCESS_KEY}'
        CSV IGNOREHEADER 1;
    """

    pq_sql = f"""
        COPY raw_data.data_parquet
        FROM 's3://{S3_BUCKET}/{parquet_key}'
        ACCESS_KEY_ID '{AWS_ACCESS_KEY_ID}'
        SECRET_ACCESS_KEY '{AWS_SECRET_ACCESS_KEY}'
        FORMAT AS PARQUET;
    """

    start_csv = time.time()
    pg.run(csv_sql)
    ti.xcom_push(key=f'{size_mb}_csv_copy_time', value=round(time.time() - start_csv, 2))

    start_pq = time.time()
    pg.run(pq_sql)
    ti.xcom_push(key=f'{size_mb}_parquet_copy_time', value=round(time.time() - start_pq, 2))

def record_metrics(size_mb: int, **kwargs):
    ti = kwargs['ti']
    pg = PostgresHook(postgres_conn_id='redshift_conn')

    metrics = [
        {
            'format': 'csv',
            'size': ti.xcom_pull(key=f'{size_mb}_csv_size'),
            'time': ti.xcom_pull(key=f'{size_mb}_csv_copy_time'),
            'key': ti.xcom_pull(key=f'{size_mb}_csv_key')
        },
        {
            'format': 'parquet',
            'size': ti.xcom_pull(key=f'{size_mb}_parquet_size'),
            'time': ti.xcom_pull(key=f'{size_mb}_parquet_copy_time'),
            'key': ti.xcom_pull(key=f'{size_mb}_parquet_key')
        }
    ]

    for m in metrics:
        pg.run("""
            INSERT INTO analytics.format_compare (run_id, format, record_count, file_size_mb, s3_key, redshift_copy_time_secs)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, parameters=(
            str(uuid.uuid4()),
            m['format'],
            ti.xcom_pull(key=f'{size_mb}_row_count'),
            m['size'],
            m['key'],
            m['time']
        ))
