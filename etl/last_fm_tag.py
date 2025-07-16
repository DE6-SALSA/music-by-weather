import os
import requests
import time
from airflow.models import Variable

# DO NOT fetch Airflow Variables at the module level!
# Fetch them inside functions, so Airflow context is available.

def get_track_info(track_name, artist_name):
    """Use track.getInfo to get detailed metadata"""
    LASTFM_API_KEY = Variable.get("LASTFM_API_KEY")
    url = "http://ws.audioscrobbler.com/2.0/"
    params = {
        "method": "track.getInfo",
        "track": track_name,
        "artist": artist_name,
        "api_key": LASTFM_API_KEY,
        "format": "json"
    }

    response = requests.get(url, params=params)
    if response.status_code == 200:
        return response.json().get("track", {})
    else:
        print(f"❌ Failed to get info for {track_name} – {artist_name}")
        return {}


def get_tracks_by_tag_range(tag, start_page=1, end_page=2):
    """Fetch tag-based track results from specific page range"""
    LASTFM_API_KEY = Variable.get("LASTFM_API_KEY")
    collected = []

    for page in range(start_page, end_page + 1):
        print(f"📄 Fetching page {page} for tag '{tag}'...")
        params = {
            "method": "tag.getTopTracks",
            "tag": tag,
            "api_key": LASTFM_API_KEY,
            "format": "json",
            "limit": 100,  # Max per page 
            "page": page
        }

        response = requests.get("http://ws.audioscrobbler.com/2.0/", params=params)
        if response.status_code != 200:
            print(f"❌ Failed to fetch page {page}")
            print(f"Status code: {response.status_code}, Response: {response.text}")
            continue

        data = response.json()
        results = data.get("tracks", {}).get("track", [])
        if not results:
            print(f"⚠️ No results on page {page}")
            break

        collected.extend(results)
        time.sleep(0.2)

    print(f"✅ Collected {len(collected)} tracks for tag '{tag}' from pages {start_page} to {end_page}")
    return collected


def process_tracks(tracks):
    """Enrich and print detailed info for a list of tracks"""
    for i, track in enumerate(tracks, start=1):
        name = track.get("name")
        artist = track.get("artist", {}).get("name") if isinstance(track.get("artist"), dict) else track.get("artist")

        info = get_track_info(name, artist)
        time.sleep(0.2)

        album = info.get("album", {}).get("title", "N/A")
        playcount = info.get("playcount", "N/A")
        duration_ms = int(info.get("duration", 0))
        duration_min = round(duration_ms / 60000, 2) if duration_ms else "N/A"
        summary = info.get("wiki", {}).get("summary", "").split("<a")[0]

        # Artist details
        artist_url = info.get("artist", {}).get("url", "N/A")
        listeners = info.get("listeners", "N/A")

        # Album art (large)
        album_images = info.get("album", {}).get("image", [])
        large_image_url = next((img["#text"] for img in album_images if img["size"] == "large"), "N/A")

        # Tags (genres or topics)
        tags = info.get("toptags", {}).get("tag", [])
        tag_list = [tag["name"] for tag in tags[:5]] if tags else []

        print(f"{i}. {name} – {artist}")
        print(f"   Album: {album}")
        print(f"   Album Art (Large): {large_image_url}")
        print(f"   Playcount: {playcount}")
        print(f"   Listeners: {listeners}")
        print(f"   Duration: {duration_min} min")
        print(f"   Artist URL: {artist_url}")
        print(f"   Track URL: {track.get('url')}")
        if tag_list:
            print(f"   Tags: {', '.join(tag_list)}")
        if summary:
            print(f"   Description: {summary.strip()[:200]}...")
        print()

