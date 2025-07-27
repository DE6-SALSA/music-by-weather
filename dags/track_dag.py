import os
import sys
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.getenv('AIRFLOW_HOME', '/opt/airflow'), 'etl'))
from etl.slack_alert import slack_alert
from track_etl import (
    extract_tracks,
    enrich_with_tags,
    save_to_s3_parquet,
    copy_to_redshift
)

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=1),
    'on_failure_callback' : slack_alert,
}

with DAG(
    dag_id='lastfm_to_s3_redshift_test_pipeline',
    default_args=default_args,
    start_date=datetime(2025, 7, 14),
    schedule_interval="*/50 * * * *",
    catchup=False,
    tags=['lastfm', 'etl'],
) as dag:

    t1 = PythonOperator(
        task_id='extract_tracks',
        python_callable=extract_tracks,
        provide_context=True
    )

    t2 = PythonOperator(
        task_id='enrich_with_tags',
        python_callable=enrich_with_tags,
        provide_context=True
    )

    t3 = PythonOperator(
        task_id='save_to_s3_parquet',
        python_callable=save_to_s3_parquet,
        provide_context=True
    )

    t4 = PythonOperator(
        task_id='copy_to_redshift',
        python_callable=copy_to_redshift,
        provide_context=True
    )

    t1 >> t2 >> t3 >> t4
