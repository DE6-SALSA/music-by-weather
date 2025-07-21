import pandas as pd
import requests
import re
import logging
from zoneinfo import ZoneInfo
from datetime import datetime, timedelta
from airflow.providers.snowflake.hooks.snowflake import SnowflakeHook
from airflow.models import Variable
import uuid
import os
#from sklearn.feature_extraction.text import TfidfVectorizer
#from sklearn.metrics.pairwise import cosine_similarity
from .bbc_weather import get_bbc_seoul_weather_summary
from .tagged_tracks_with_lyrics import get_tracks_with_lyrics_by_tag

# All ETL logic for weather/music pipeline goes here

def get_weather_headline(**kwargs):
    # No parameters needed for this function
    headline = get_bbc_seoul_weather_summary()
    kwargs['ti'].xcom_push(key='headline', value=headline)

def get_tagged_tracks_with_lyrics(tag, start_page, end_page, max_tracks, **kwargs):
    ti = kwargs['ti']
    results = get_tracks_with_lyrics_by_tag(tag, start_page, end_page, max_tracks)
    df = pd.DataFrame(results)
    if df.empty:
        raise ValueError("No tracks with lyrics were retrieved. Cannot continue.")
    now_kst = datetime.now(ZoneInfo("Asia/Seoul"))
    filename = f"/tmp/tracks_{now_kst.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}.csv"
    print(f"Saved DataFrame with shape {df.shape} to {filename}")
    df.to_csv(filename, index=False)
    ti.xcom_push(key='tracks_csv', value=filename)

def compute_tfidf_similarity(**kwargs):
    ti = kwargs['ti']
    headline = ti.xcom_pull(key='headline', task_ids='get_weather_headline')
    csv_path = ti.xcom_pull(key='tracks_csv', task_ids='get_tagged_tracks_with_lyrics')
    df = pd.read_csv(csv_path)
    documents = [headline] + df["lyrics"].fillna("").tolist()
    vectorizer = TfidfVectorizer(stop_words="english")
    tfidf_matrix = vectorizer.fit_transform(documents)
    similarities = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:]).flatten()
    df["similarity_to_headline"] = similarities
    df_sorted = df.sort_values(by="similarity_to_headline", ascending=False)
    new_filename = csv_path.replace("tracks", "ranked_tracks")
    df_sorted.to_csv(new_filename, index=False)
    ti.xcom_push(key='ranked_csv', value=new_filename)

def copy_to_snowflake(**kwargs):
    ti = kwargs['ti']
    local_file = ti.xcom_pull(key='ranked_csv', task_ids='compute_tfidf_similarity')
    df = pd.read_csv(local_file)
    df = df.fillna({
        'name': 'Unknown',
        'artist': 'Unknown', 
        'album': 'Unknown',
        'playcount': 0,
        'duration_min': 0.0,
        'summary': '',
        'track_url': '',
        'lyrics': '',
        'similarity_to_headline': 0.0
    })
    snowflake_hook = SnowflakeHook(snowflake_conn_id='snowflake_conn')
    TABLE_NAME = "WEATHER_MUSIC_MATCH"
    TABLE_SCHEMA = "ADHOC"
    snowflake_hook.run(f"TRUNCATE TABLE {TABLE_SCHEMA}.{TABLE_NAME}")
    insert_sql = f"""
    INSERT INTO {TABLE_SCHEMA}.{TABLE_NAME} (
        name, artist, album, playcount, duration_min,
        summary, track_url, lyrics, similarity_to_headline
    ) VALUES (
        %(name)s, %(artist)s, %(album)s, %(playcount)s, %(duration_min)s,
        %(summary)s, %(track_url)s, %(lyrics)s, %(similarity_to_headline)s
    )
    """
    for _, row in df.iterrows():
        snowflake_hook.run(insert_sql, parameters=row.to_dict()) 
