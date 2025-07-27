from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.models import Variable
from datetime import datetime, timedelta
import logging
import boto3
from zoneinfo import ZoneInfo

def copy_all_to_redshift_dedup(**kwargs):
    logging.info("Start copy_all_to_redshift_dedup")

    # Credentials and config
    aws_access_key_id = Variable.get("S3_ACCESS_KEY")
    aws_secret_access_key = Variable.get("S3_SECRET_KEY")
    s3_bucket = Variable.get("S3_BUCKET_NAME")
    s3_prefix = "ml_data"
    weather_conditions = ["Snowy", "Stormy", "Rainy", "Cold", "Hot", "Windy", "Cloudy", "Clear"]

    # Redshift setup
    track_table = "weather_music_track"
    track_schema = "raw_data"
    target_table = "weather_music"
    target_schema = "analytics_data"
    
    columns = [
        "region", "headline", "weather", "weather_tag", "track_name", "track_url", "artist_name",
        "playcount", "listeners", "album_title", "album_url", "album_image_url",
        "lyrics", "run_time", "similarity_to_headline"
    ]
    col_str = ", ".join(columns)

    now_kst = datetime.now(ZoneInfo("Asia/Seoul"))
    date_str = now_kst.strftime("%y-%m-%d")

    s3 = boto3.client(
        's3',
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key
    )

    hook = PostgresHook(postgres_conn_id='redshift_conn')

    for condition in weather_conditions:
        s3_key = f"{s3_prefix}/{condition}_uploaded_{date_str}.csv"

        try:
            s3.head_object(Bucket=s3_bucket, Key=s3_key)
            logging.info(f"📁 Found file in S3: s3://{s3_bucket}/{s3_key}")
        except s3.exceptions.ClientError:
            logging.warning(f"⏭️ Skipping {s3_key}: Not found.")
            continue

        # Truncate staging table
        hook.run(f"TRUNCATE TABLE {track_schema}.{track_table};")

        # COPY into staging
        copy_sql = f"""
            COPY {track_schema}.{track_table} ({col_str})
            FROM 's3://{s3_bucket}/{s3_key}'
            ACCESS_KEY_ID '{aws_access_key_id}'
            SECRET_ACCESS_KEY '{aws_secret_access_key}'
            CSV
            IGNOREHEADER 1
            NULL AS 'N/A'
            REGION 'ap-northeast-2';
        """
        logging.info(f"📥 Executing COPY to staging for {condition}: {s3_key}")
        hook.run(copy_sql)

        # INSERT with deduplication
        insert_sql = f"""
            INSERT INTO {target_schema}.{target_table} ({col_str})
            SELECT s.{', s.'.join(columns)}
            FROM {track_schema}.{track_table} s
            LEFT JOIN {target_schema}.{target_table} m
              ON s.track_name = m.track_name
             AND s.artist_name = m.artist_name
             AND s.region = m.region
             AND CAST(s.run_time AS DATE) = CAST(m.run_time AS DATE)
            WHERE m.track_name IS NULL;
        """
        logging.info(f"🔁 Inserting deduplicated data into target table for {condition}")
        hook.run(insert_sql)
        logging.info(f"✅ Finished inserting {condition} into {target_table}")

# DAG definition
default_args = {
    'owner': 'airflow',
    'retries': 1,
    'retry_delay': timedelta(minutes=3)
}

with DAG(
    dag_id='ml_redshift_dedup',
    default_args=default_args,
    start_date=datetime(2025, 7, 22),
    schedule_interval='0 */2 * * *',
    catchup=False,
    description='Deduplicated load of all weather condition music CSVs from S3 to Redshift'
) as dag:

    copy_all_to_redshift_task = PythonOperator(
        task_id='copy_all_to_redshift_dedup',
        python_callable=copy_all_to_redshift_dedup,
        execution_timeout=timedelta(minutes=15)
    )
