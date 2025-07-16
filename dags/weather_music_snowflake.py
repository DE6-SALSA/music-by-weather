from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import sys
import os
# Ensure etl module is importable
sys.path.append(os.path.join(os.path.dirname(__file__), '../etl'))
from lyrics_etl import get_weather_headline, get_tagged_tracks_with_lyrics, compute_tfidf_similarity, copy_to_snowflake

# === User-configurable parameters ===
TAG = "thunder"
START_PAGE = 1
END_PAGE = 1
MAX_TRACKS = 50
# ====================================

default_args = {
    'owner': 'airflow',
    'retries': 1,
    'retry_delay': timedelta(minutes=1),
}

with DAG(
    dag_id='weather_music_to_snowflake_pipeline',
    default_args=default_args,
    start_date=datetime(2025, 7, 14),
    schedule_interval='@daily',
    catchup=False,
    description='TF-IDF weather-aware music matching into Snowflake (no S3)'
) as dag:
    # All business logic is in etl/weather_etl.py
    t1 = PythonOperator(
        task_id='get_weather_headline',
        python_callable=get_weather_headline
    )
    t2 = PythonOperator(
        task_id='get_tagged_tracks_with_lyrics',
        python_callable=get_tagged_tracks_with_lyrics,
        op_kwargs={
            'tag': TAG,
            'start_page': START_PAGE,
            'end_page': END_PAGE,
            'max_tracks': MAX_TRACKS
        }
    )
    t3 = PythonOperator(
        task_id='compute_tfidf_similarity',
        python_callable=compute_tfidf_similarity
    )
    t5 = PythonOperator(
        task_id='copy_to_snowflake',
        python_callable=copy_to_snowflake
    )
    t1 >> t2 >> t3 >> t5 
