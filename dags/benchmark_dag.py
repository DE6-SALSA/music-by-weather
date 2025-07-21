import os
import sys
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
sys.path.insert(0, os.path.join(os.getenv('AIRFLOW_HOME','/opt/airflow'), 'etl'))

from track_etl import extract_tracks, enrich_with_tags
from format_etl import (
    save_csv_to_s3,
    save_parquet_to_s3,
    copy_csv_to_redshift,
    copy_parquet_to_redshift,
    record_csv_result,
    record_parquet_result
)

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=2)
}
#test
dag = DAG(
    dag_id='format_comparison_benchmark',
    description='Benchmark CSV vs Parquet format for Redshift ingestion',
    default_args=default_args,
    schedule_interval=None,
    start_date=datetime(2025, 7, 20),
    catchup=False,
    tags=['benchmark', 'format', 'csv', 'parquet']
)

with dag:
    t1 = PythonOperator(
        task_id='extract_tracks',
        python_callable=extract_tracks
    )

    t2 = PythonOperator(
        task_id='enrich_with_tags',
        python_callable=enrich_with_tags
    )

    t3 = PythonOperator(
        task_id='save_csv_to_s3',
        python_callable=save_csv_to_s3
    )

    t4 = PythonOperator(
        task_id='save_parquet_to_s3',
        python_callable=save_parquet_to_s3
    )

    t5 = PythonOperator(
        task_id='copy_csv_to_redshift',
        python_callable=copy_csv_to_redshift
    )

    t6 = PythonOperator(
        task_id='copy_parquet_to_redshift',
        python_callable=copy_parquet_to_redshift
    )

    t7 = PythonOperator(
        task_id='record_csv_result',
        python_callable=record_csv_result
    )

    t8 = PythonOperator(
        task_id='record_parquet_result',
        python_callable=record_parquet_result
    )

    t1 >> t2 >> [t3, t4]
    t3 >> t5 >> t7
    t4 >> t6 >> t8
