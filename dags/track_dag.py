import os
import sys
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
#testing
sys.path.insert(0, os.path.join(os.getenv('AIRFLOW_HOME','/opt/airflow'), 'etl'))

from track_etl import (
    extract_tracks,
    enrich_with_tags,
    save_to_s3_csv,
    copy_to_redshift
)

default_args = {
    'owner': 'airflow',
    'retries': 1,
    'retry_delay': timedelta(minutes=1),
}

with DAG(
    dag_id='lastfm_to_s3_redshift_test_pipeline',
    default_args=default_args,
    start_date=datetime(2025, 7, 14),
    schedule_interval="*/50 * * * *",
    catchup=False,
    tags=['lastfm','etl']
) as dag:

    t1 = PythonOperator(task_id='extract_tracks', python_callable=extract_tracks)
    t2 = PythonOperator(task_id='enrich_with_tags', python_callable=enrich_with_tags)
    t3 = PythonOperator(task_id='save_to_s3_csv', python_callable=save_to_s3_csv)
    t4 = PythonOperator(task_id='copy_to_redshift', python_callable=copy_to_redshift)

    t1 >> t2 >> t3 >> t4

