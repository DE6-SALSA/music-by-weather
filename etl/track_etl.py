import logging
import os
import time
import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import requests
from airflow.models import Variable
from airflow.providers.amazon.aws.hooks.s3 import S3Hook
from airflow.providers.postgres.hooks.postgres import PostgresHook

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

API_KEY               = Variable.get("LASTFM_API_KEY")
BASE_URL              = "http://ws.audioscrobbler.com/2.0/"
S3_BUCKET             = Variable.get("S3_BUCKET_NAME")
AWS_ACCESS_KEY_ID     = Variable.get("S3_ACCESS_KEY")
AWS_SECRET_ACCESS_KEY = Variable.get("S3_SECRET_KEY")
TABLE_SCHEMA          = "raw_data"
TABLE_NAME            = "top_tag5"
LAST_PAGE_KEY         = "LAST_PAGE"

COLUMNS = [
    "artist", "title",
    "play_cnt", "listener_cnt",
    "tag1", "tag2", "tag3", "tag4", "tag5"
]

def extract_tracks(**kwargs):
    logging.info("Start extract_tracks")
    tracks = []
    limit = 100
    start_page = int(Variable.get(LAST_PAGE_KEY, default_var=1))
    end_page = start_page + 2

    for page in range(start_page, end_page + 1):
        logging.info(f"  Fetching chart.getTopTracks page={page}")
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

    Variable.set(LAST_PAGE_KEY, end_page + 1)
    logging.info(f"  Pulled {len(tracks)} tracks, next page set to {end_page+1}")
    kwargs['ti'].xcom_push(key='tracks', value=tracks)
    logging.info("Finished extract_tracks")

def enrich_with_tags(**kwargs):
    logging.info("Start enrich_with_tags")
    ti = kwargs['ti']
    tracks = ti.xcom_pull(key='tracks')
    logging.info(f"  Retrieved {len(tracks)} tracks from XCom")
    enriched = []

    for artist, title in tracks:
        logging.info(f"    Enriching: {artist} / {title}")
        params = {
            "method": "track.getInfo",
            "artist": artist,
            "track": title,
            "api_key": API_KEY,
            "format": "json"
        }
        try:
            resp = requests.get(BASE_URL, params=params)
            info = resp.json().get('track', {})
            tags = [tag['name'] for tag in info.get('toptags', {}).get('tag', [])][:5]
            tags += [None] * (5 - len(tags))
            playcount = int(info.get('playcount', 0))
            listeners = int(info.get('listeners', 0))
        except Exception as e:
            logging.warning(f"      Error for {artist}-{title}: {e}")
            playcount = listeners = 0
            tags = [None]*5

        enriched.append((artist, title, playcount, listeners, *tags))
        time.sleep(0.2)

    logging.info(f"  Enriched total {len(enriched)} records")
    ti.xcom_push(key='enriched_tracks', value=enriched)
    logging.info("Finished enrich_with_tags")

def save_to_s3_csv(**kwargs):
    logging.info("Start save_to_s3_csv")
    ti = kwargs['ti']
    enriched = ti.xcom_pull(key='enriched_tracks')
    df = pd.DataFrame(enriched, columns=COLUMNS)

    now_kst = datetime.now(ZoneInfo("Asia/Seoul"))
    filename = f"track_data_{now_kst:%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:8]}.csv"
    local_path = f"/tmp/{filename}"

    logging.info(f"  Writing {len(df)} rows to {local_path}")
    df.to_csv(local_path, index=False)

    s3_key = f"track_data/{filename}"
    logging.info(f"  Uploading to s3://{S3_BUCKET}/{s3_key}")
    S3Hook(aws_conn_id='aws_s3_conn') \
        .load_file(filename=local_path, key=s3_key, bucket_name=S3_BUCKET, replace=True)

    ti.xcom_push(key='s3_key', value=s3_key)
    os.remove(local_path)
    logging.info(" Finished save_to_s3_csv")


def copy_to_redshift(**kwargs):
    logging.info("Start copy_to_redshift")
    ti = kwargs['ti']
    s3_key = ti.xcom_pull(key='s3_key')

    col_str = ", ".join(COLUMNS)

    truncate_staging_sql = "TRUNCATE TABLE raw_data.top_tag5_staging;"

    copy_sql = f"""
        COPY raw_data.top_tag5_staging ({col_str})
        FROM 's3://{S3_BUCKET}/{s3_key}'
        ACCESS_KEY_ID '{AWS_ACCESS_KEY_ID}'
        SECRET_ACCESS_KEY '{AWS_SECRET_ACCESS_KEY}'
        CSV IGNOREHEADER 1;
    """

    merge_sql = """
        INSERT INTO raw_data.top_tag5 (artist, title, play_cnt, listener_cnt, tag1, tag2, tag3, tag4, tag5, load_time)
        SELECT s.artist, s.title, s.play_cnt, s.listener_cnt, s.tag1, s.tag2, s.tag3, s.tag4, s.tag5, current_timestamp
        FROM raw_data.top_tag5_staging s
        LEFT JOIN raw_data.top_tag5 t
        ON s.artist = t.artist AND s.title = t.title
        WHERE t.artist IS NULL;
    """

    hook = PostgresHook(postgres_conn_id='redshift_conn')
    hook.run(truncate_staging_sql)
    hook.run(copy_sql)
    hook.run(merge_sql)
    logging.info("Finished copy_to_redshift with staging + deduplication insert")
