import os
import sys

from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
sys.path.insert(0, os.path.join(os.getenv('AIRFLOW_HOME','/opt/airflow'), 'etl'))

from dummy_benchmark import (
    generate_dummy_csv_parquet,
    upload_to_s3,
    copy_to_redshift,
    record_metrics,
)

default_args = {
    'owner': 'airflow',
    'retries': 1,
    'retry_delay': timedelta(minutes=2),
}

dummy_sizes_mb = [1, 10, 50, 100, 200]

with DAG(
    dag_id='dummy_format_comparison_benchmark',
    default_args=default_args,
    start_date=datetime(2025, 7, 23),
    schedule_interval=None,
    catchup=False,
    tags=['benchmark', 'format'],
) as dag:

    for size in dummy_sizes_mb:
        for fmt in ['csv', 'parquet']:
            generate = PythonOperator(
                task_id=f'generate_{fmt}_{size}mb',
                python_callable=generate_dummy_csv_parquet,
                op_kwargs={'size_mb': size, 'format_type': fmt},
            )

            upload = PythonOperator(
                task_id=f'upload_{fmt}_{size}mb_to_s3',
                python_callable=upload_to_s3,
                op_kwargs={'size_mb': size, 'format_type': fmt},
            )

            copy = PythonOperator(
                task_id=f'copy_{fmt}_{size}mb_to_redshift',
                python_callable=copy_to_redshift,
                op_kwargs={'size_mb': size, 'format_type': fmt},
            )

            record = PythonOperator(
                task_id=f'record_metrics_{fmt}_{size}mb',
                python_callable=record_metrics,
                op_kwargs={'size_mb': size, 'format_type': fmt},
            )

            generate >> upload >> copy >> record
