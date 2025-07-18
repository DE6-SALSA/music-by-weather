from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago
from airflow.utils.task_group import TaskGroup
from datetime import timedelta

from airflow.models import Variable

from airflow.utils.dates import datetime

def push_message_to_xcom(**kwargs):
    return 'testing actions step by step 4'

with DAG(
    dag_id='test_dag',
    schedule_interval=timedelta(days=1),
    start_date=days_ago(1),
    catchup=False,
    tags=['test', 'private_ec2'],
) as dag:
    simple_task = PythonOperator(
        task_id='push_message',
        python_callable=push_message_to_xcom,
        provide_context=True,
    )
    simple_task
