import os
import time
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from airflow.models import Variable
from airflow.providers.amazon.aws.hooks.s3 import S3Hook
from airflow.providers.postgres.hooks.postgres import PostgresHook
##test

API_KEY = Variable.get("LASTFM_API_KEY")
S3_BUCKET = Variable.get("S3_BUCKET_NAME")
AWS_ACCESS_KEY_ID = Variable.get("S3_ACCESS_KEY")
AWS_SECRET_ACCESS_KEY = Variable.get("S3_SECRET_KEY")

COLUMNS = [
    "artist", "title", "play_cnt", "listener_cnt",
    "tag1", "tag2", "tag3", "tag4", "tag5","created_at"
]

def save_csv_to_s3(**kwargs):
    ti = kwargs['ti']
    enriched = ti.xcom_pull(key='enriched_tracks')
    df = pd.DataFrame(enriched, columns=COLUMNS[:-1])
    df["created_at"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    df = df[COLUMNS]

    now = datetime.now(ZoneInfo("Asia/Seoul"))
    filename = f"track_data_{now:%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:6]}.csv"
    local_path = f"/tmp/{filename}"
    df.to_csv(local_path, index=False)

    s3_key = f"format_data/csv/{filename}"
    S3Hook(aws_conn_id='aws_s3_conn').load_file(
        filename=local_path,
        key=s3_key,
        bucket_name=S3_BUCKET,
        replace=True
    )

    ti.xcom_push(key='s3_key_csv', value=s3_key)
    ti.xcom_push(key='csv_row_count', value=len(df))
    ti.xcom_push(key='csv_file_size', value=os.path.getsize(local_path) / 1024**2)
    os.remove(local_path)


def save_parquet_to_s3(**kwargs):
    ti = kwargs['ti']
    enriched = ti.xcom_pull(key='enriched_tracks')
    df = pd.DataFrame(enriched, columns=COLUMNS[:-1])

    df["created_at"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    now = datetime.now(ZoneInfo("Asia/Seoul"))
    filename = f"track_data_{now:%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:6]}.parquet"
    local_path = f"/tmp/{filename}"

    table = pa.Table.from_pandas(df)
    pq.write_table(table, local_path, compression='snappy')

    s3_key = f"format_data/parquet/{filename}"
    S3Hook(aws_conn_id='aws_s3_conn').load_file(
        filename=local_path,
        key=s3_key,
        bucket_name=S3_BUCKET,
        replace=True
    )

    ti.xcom_push(key='s3_key_parquet', value=s3_key)
    ti.xcom_push(key='parquet_row_count', value=len(df))
    ti.xcom_push(key='parquet_file_size', value=os.path.getsize(local_path) / 1024**2)

    os.remove(local_path)



def copy_csv_to_redshift(**kwargs):
    ti = kwargs['ti']
    s3_key = ti.xcom_pull(key='s3_key_csv')
    start = time.time()

    sql = f"""
        COPY raw_data.data_csv ({', '.join(COLUMNS)})
        FROM 's3://{S3_BUCKET}/{s3_key}'
        ACCESS_KEY_ID '{AWS_ACCESS_KEY_ID}'
        SECRET_ACCESS_KEY '{AWS_SECRET_ACCESS_KEY}'
        CSV IGNOREHEADER 1;
    """
    PostgresHook(postgres_conn_id='redshift_conn').run(sql)
    elapsed = round(time.time() - start, 2)
    ti.xcom_push(key='csv_copy_time', value=elapsed)

def copy_parquet_to_redshift(**kwargs):
    ti = kwargs['ti']
    s3_key = ti.xcom_pull(key='s3_key_parquet')
    start = time.time()

    sql = f"""
        COPY raw_data.data_parquet ({', '.join(COLUMNS)})
        FROM 's3://{S3_BUCKET}/{s3_key}'
        ACCESS_KEY_ID '{AWS_ACCESS_KEY_ID}'
        SECRET_ACCESS_KEY '{AWS_SECRET_ACCESS_KEY}'
        FORMAT AS PARQUET;
    """
    PostgresHook(postgres_conn_id='redshift_conn').run(sql)
    elapsed = round(time.time() - start, 2)
    ti.xcom_push(key='parquet_copy_time', value=elapsed)

def record_csv_result(**kwargs):
    ti = kwargs['ti']
    pg = PostgresHook(postgres_conn_id='redshift_conn')
    pg.run("""
        INSERT INTO analytics.format_compare (run_id, format, record_count, file_size_mb, s3_key, redshift_copy_time_secs)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, parameters=(
        str(uuid.uuid4()),
        'csv',
        ti.xcom_pull(key='csv_row_count'),
        ti.xcom_pull(key='csv_file_size'),
        ti.xcom_pull(key='s3_key_csv'),
        ti.xcom_pull(key='csv_copy_time')
    ))

def record_parquet_result(**kwargs):
    ti = kwargs['ti']
    pg = PostgresHook(postgres_conn_id='redshift_conn')
    pg.run("""
        INSERT INTO analytics.format_compare (run_id, format, record_count, file_size_mb, s3_key, redshift_copy_time_secs)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, parameters=(
        str(uuid.uuid4()),
        'parquet',
        ti.xcom_pull(key='parquet_row_count'),
        ti.xcom_pull(key='parquet_file_size'),
        ti.xcom_pull(key='s3_key_parquet'),
        ti.xcom_pull(key='parquet_copy_time')
    ))
