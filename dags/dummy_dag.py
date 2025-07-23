from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
from format_benchmark_etl import (
    generate_dummy_csv_parquet,
    upload_to_s3,
    copy_to_redshift,
    record_metrics
)

default_args = {
    'owner': 'airflow',
    'retries': 1,
    'retry_delay': timedelta(minutes=2),
}

dummy_sizes_mb = [1, 10, 100, 300, 500, 1000] 

with DAG(
    dag_id='format_comparison_benchmark',
    default_args=default_args,
    start_date=datetime(2025, 7, 23),
    schedule_interval=None,
    catchup=False,
    tags=['benchmark', 'format'],
) as dag:

    for size in dummy_sizes_mb:
        generate = PythonOperator(
            task_id=f'generate_{size}mb_data',
            python_callable=generate_dummy_csv_parquet,
            op_kwargs={'size_mb': size},
        )

        upload = PythonOperator(
            task_id=f'upload_{size}mb_to_s3',
            python_callable=upload_to_s3,
            op_kwargs={'size_mb': size},
        )

        copy = PythonOperator(
            task_id=f'copy_{size}mb_to_redshift',
            python_callable=copy_to_redshift,
            op_kwargs={'size_mb': size},
        )

        record = PythonOperator(
            task_id=f'record_metrics_{size}mb',
            python_callable=record_metrics,
            op_kwargs={'size_mb': size},
        )

        generate >> upload >> copy >> record
