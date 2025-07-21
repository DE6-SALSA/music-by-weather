from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.models import Variable
from datetime import datetime, timedelta
from airflow.providers.amazon.aws.hooks.s3 import S3Hook

import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))
from etl.weather_etl import fetch_weather_data, upload_to_s3, copy_to_redshift
# from etl.slack_alert import slack_alert

COORDINATES_PATH = '/opt/airflow/data/coordinates.csv'
WEATHER_API_KEY =  Variable.get("WEATHER_API_KEY")
S3_BUCKET = Variable.get("S3_BUCKET_NAME")
AWS_ACCESS_KEY_ID = Variable.get("S3_ACCESS_KEY")
AWS_SECRET_ACCESS_KEY = Variable.get("S3_SECRET_KEY")

default_args = {
    'owner': 'airflow',
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
    'on_failure_callback' : slack_alert
}

with DAG(
    dag_id='weather_pipeline',
    default_args=default_args,
    description='weather data → S3 → Redshift DAG',
    schedule_interval='40 * * * *',
    start_date=datetime(2025, 7, 11),
    catchup=False,
    tags=['weather', 's3']
) as dag:

    fetch_task = PythonOperator(
        task_id='fetch_weather_data',
        python_callable=fetch_weather_data,
        op_kwargs={
            'csv_path': COORDINATES_PATH,
            'service_key': WEATHER_API_KEY
        }
    )

    upload_task = PythonOperator(
        task_id='upload_to_s3',
        python_callable=upload_to_s3,
        op_kwargs={
            'bucket_name': S3_BUCKET,
            'aws_conn_id': 'aws_s3_conn' 
        }
    )

    copy_task = PythonOperator(
        task_id='copy_to_redshift',
        python_callable=copy_to_redshift,
        op_kwargs={
            'redshift_conn_id': 'redshift_conn',
            'table_name': 'raw_data.weather_data',
            's3_bucket': S3_BUCKET,
            'aws_access_key_id': AWS_ACCESS_KEY_ID,
            'aws_secret_access_key': AWS_SECRET_ACCESS_KEY
        }
    )

    fetch_task >> upload_task >> copy_task
