import logging
import os
import time
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import requests
from airflow.models import Variable
from airflow.providers.amazon.aws.hooks.s3 import S3Hook
from airflow.providers.postgres.hooks.postgres import PostgresHook

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
###
API_KEY               = Variable.get("LASTFM_API_KEY")
BASE_URL              = "http://ws.audioscrobbler.com/2.0/"
S3_BUCKET             = Variable.get("S3_BUCKET_NAME")
AWS_ACCESS_KEY_ID     = Variable.get("S3_ACCESS_KEY")
AWS_SECRET_ACCESS_KEY = Variable.get("S3_SECRET_KEY")
LAST_PAGE_KEY         = "LAST_PAGE"

COLUMNS = [
    "artist", "title",
    "play_cnt", "listener_cnt",
    "tag1", "tag2", "tag3", "tag4", "tag5"
]

def extract_tracks(**kwargs):
    logging.info("Start extract_tracks")
    tracks = []
    limit = 50
    start_page = int(Variable.get(LAST_PAGE_KEY, default_var=1))
    end_page = start_page + 2

    for page in range(start_page, end_page + 1):
        params = {
            "method": "chart.getTopTracks",
            "api_key": API_KEY,
            "format": "json",
            "limit": limit,
            "page": page
        }
        resp = requests.get(BASE_URL, params=params)
        for t in resp.json().get('tracks', {}).get('track', []):
            tracks.append((t['artist']['name'], t['name']))
        time.sleep(0.2)

    next_page = end_page + 1 if end_page + 1 <= 200 else 1
    Variable.set(LAST_PAGE_KEY, next_page)
    kwargs['ti'].xcom_push(key='tracks', value=tracks)
    logging.info(f"Extracted {len(tracks)} tracks. Next page: {next_page}")


def enrich_with_tags(**kwargs):
    logging.info("Start enrich_with_tags")
    ti = kwargs['ti']
    tracks = ti.xcom_pull(key='tracks')
    enriched = []
    pg_hook = PostgresHook(postgres_conn_id='redshift_conn')

    for artist, title in tracks:
        try:
            params = {
                "method": "track.getInfo",
                "artist": artist,
                "track": title,
                "api_key": API_KEY,
                "format": "json"
            }
            resp = requests.get(BASE_URL, params=params)
            info = resp.json().get('track', {})
            tags = [tag['name'] for tag in info.get('toptags', {}).get('tag', [])][:5]
            tags += [None] * (5 - len(tags))
            playcount = int(info.get('playcount', 0))
            listeners = int(info.get('listeners', 0))
        except Exception as e:
            logging.warning(f"Error for {artist}-{title}: {e}")
            pg_hook.run(
                """
                INSERT INTO raw_data.track_out (artist, title, reason, dropped_at)
                VALUES (%s, %s, %s, current_timestamp);
                """, parameters=(artist, title, "fetch_error")
            )
            playcount = listeners = 0
            tags = [None] * 5

        enriched.append((artist, title, playcount, listeners, *tags))
        time.sleep(0.2)

    ti.xcom_push(key='enriched_tracks', value=enriched)
    logging.info(f"Enriched {len(enriched)} tracks")


def save_to_s3_parquet(**kwargs):
    logging.info("Start save_to_s3_parquet")
    ti = kwargs['ti']
    enriched = ti.xcom_pull(key='enriched_tracks')
    df = pd.DataFrame(enriched, columns=COLUMNS)

    now_kst = datetime.now(ZoneInfo("Asia/Seoul"))
    filename = f"track_data_{now_kst:%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:8]}.parquet"
    local_path = f"/tmp/{filename}"

    df.to_parquet(local_path, engine="pyarrow", index=False, compression="snappy")

    s3_key = f"track_data/{filename}"
    S3Hook(aws_conn_id='aws_s3_conn').load_file(
        filename=local_path,
        key=s3_key,
        bucket_name=S3_BUCKET,
        replace=True
    )

    ti.xcom_push(key='s3_key', value=s3_key)
    os.remove(local_path)
    logging.info(f"Uploaded to S3: {s3_key}")


def copy_to_redshift(**kwargs):
    logging.info("Start copy_to_redshift")
    ti = kwargs['ti']
    s3_key = ti.xcom_pull(key='s3_key')
    col_str = ", ".join(COLUMNS)

    hook = PostgresHook(postgres_conn_id='redshift_conn')

    hook.run(f"""
        TRUNCATE TABLE raw_data.track_data;
        COPY raw_data.track_data ({col_str})
        FROM 's3://{S3_BUCKET}/{s3_key}'
        ACCESS_KEY_ID '{AWS_ACCESS_KEY_ID}'
        SECRET_ACCESS_KEY '{AWS_SECRET_ACCESS_KEY}'
        FORMAT AS PARQUET;
    """)

    update_sql = """
        UPDATE analytics_data.top_tag5 AS tgt
        SET play_cnt = src.play_cnt,
            listener_cnt = src.listener_cnt,
            tag1 = src.tag1,
            tag2 = src.tag2,
            tag3 = src.tag3,
            tag4 = src.tag4,
            tag5 = src.tag5,
            load_time = GETDATE() AT TIME ZONE 'Asia/Seoul'
        FROM raw_data.track_data AS src
        WHERE tgt.artist = src.artist
          AND tgt.title = src.title
          AND (tgt.play_cnt <> src.play_cnt OR tgt.listener_cnt <> src.listener_cnt);
    """
    hook.run(update_sql)

    insert_sql = """
        INSERT INTO analytics_data.top_tag5 (
            artist, title, play_cnt, listener_cnt,
            tag1, tag2, tag3, tag4, tag5, load_time
        )
        SELECT src.artist, src.title, src.play_cnt, src.listener_cnt,
               src.tag1, src.tag2, src.tag3, src.tag4, src.tag5,
               GETDATE() AT TIME ZONE 'Asia/Seoul'
        FROM raw_data.track_data AS src
        LEFT JOIN analytics_data.top_tag5 AS tgt
          ON src.artist = tgt.artist AND src.title = tgt.title
        WHERE tgt.artist IS NULL
          AND src.artist IS NOT NULL AND src.artist <> ''
          AND src.title IS NOT NULL AND src.title <> ''
          AND src.play_cnt >= 0
          AND src.listener_cnt >= 0
          AND NOT (src.tag1 IS NULL AND src.tag2 IS NULL AND src.tag3 IS NULL AND src.tag4 IS NULL AND src.tag5 IS NULL);
    """
    hook.run(insert_sql)

    invalid_sql = """
        INSERT INTO raw_data.bad_records_top_tag5 (
            artist, title, play_cnt, listener_cnt,
            tag1, tag2, tag3, tag4, tag5,
            error_reason, load_time
        )
        SELECT artist, title, play_cnt, listener_cnt,
               tag1, tag2, tag3, tag4, tag5,
               CASE
                   WHEN artist IS NULL OR artist = '' THEN 'invalid artist'
                   WHEN title IS NULL OR title = '' THEN 'invalid title'
                   WHEN play_cnt < 0 THEN 'negative play_cnt'
                   WHEN listener_cnt < 0 THEN 'negative listener_cnt'
                   WHEN tag1 IS NULL AND tag2 IS NULL AND tag3 IS NULL AND tag4 IS NULL AND tag5 IS NULL THEN 'no tags'
                   ELSE 'unknown'
               END AS error_reason,
               GETDATE() AT TIME ZONE 'Asia/Seoul'
        FROM raw_data.track_data
        WHERE artist IS NULL OR artist = ''
           OR title IS NULL OR title = ''
           OR play_cnt < 0
           OR listener_cnt < 0
           OR (tag1 IS NULL AND tag2 IS NULL AND tag3 IS NULL AND tag4 IS NULL AND tag5 IS NULL);
    """
    hook.run(invalid_sql)

    logging.info("Finished copy_to_redshift with UPDATE+INSERT logic")
