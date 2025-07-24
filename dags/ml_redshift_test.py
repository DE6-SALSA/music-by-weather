from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.models import Variable
from datetime import datetime, timedelta
import logging
import boto3
from zoneinfo import ZoneInfo

def copy_all_to_redshift(**kwargs):
    logging.info("🚀 Start copy_all_to_redshift")

    # Credentials and config
    aws_access_key_id = Variable.get("S3_ACCESS_KEY")
    aws_secret_access_key = Variable.get("S3_SECRET_KEY")
    s3_bucket = Variable.get("S3_BUCKET_NAME")
    s3_prefix = "ml_data"
    weather_conditions = ["Snowy", "Stormy", "Rainy", "Cold", "Hot", "Windy", "Cloudy", "Clear"]

    # Redshift setup
    table_name = "weather_music"
    table_schema = "raw_data"
    columns = [
        "region", "headline", "weather", "weather_tag","track_name", "track_url", "artist_name",
        "playcount", "listeners", "album_title", "album_url", "album_image_url",
        "lyrics","run_time", "similarity_to_headline"
        ]
    col_str = ", ".join(columns)

    # Today's date string (YY-MM-DD)
    now_kst = datetime.now(ZoneInfo("Asia/Seoul"))
    date_str = now_kst.strftime("%y-%m-%d")

    # Initialize S3 client
    s3 = boto3.client(
        's3',
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key
    )

    hook = PostgresHook(postgres_conn_id='redshift_conn')

    for condition in weather_conditions:
        s3_key = f"{s3_prefix}/{condition}_uploaded_{date_str}.csv"

        # Check if file exists in S3
        try:
            s3.head_object(Bucket=s3_bucket, Key=s3_key)
            logging.info(f"📁 Found file in S3: s3://{s3_bucket}/{s3_key}")
        except s3.exceptions.ClientError:
            logging.warning(f"⏭️ Skipping {s3_key}: Not found.")
            continue

        copy_sql = f"""
            COPY {table_schema}.{table_name} ({col_str})
            FROM 's3://{s3_bucket}/{s3_key}'
            ACCESS_KEY_ID '{aws_access_key_id}'
            SECRET_ACCESS_KEY '{aws_secret_access_key}'
            CSV
            IGNOREHEADER 1
            NULL AS 'N/A'
            REGION 'ap-northeast-2';
        """

        logging.info(f"📥 Executing COPY for {condition}: {s3_key}")
        logging.info(f"COPY SQL:\n{copy_sql}")
        try:
            hook.run(copy_sql)
            logging.info(f"✅ Finished copying {s3_key} to {table_schema}.{table_name}")
        except Exception as e:
            logging.error(f"❌ COPY failed for {s3_key}: {e}")

# DAG definition
default_args = {
    'owner': 'airflow',
    'retries': 1,
    'retry_delay': timedelta(minutes=3)
}

with DAG(
    dag_id='ml_s32_redshift',
    default_args=default_args,
    start_date=datetime(2025, 7, 22),
    schedule_interval='0 3 * * *',  # 12:00 PM KST daily
    catchup=False,
    description='Load all weather condition music CSVs from S3 into Redshift'
) as dag:

    copy_all_to_redshift_task = PythonOperator(
        task_id='copy_all_to_redshift',
        python_callable=copy_all_to_redshift,
        execution_timeout=timedelta(minutes=10)
    )
