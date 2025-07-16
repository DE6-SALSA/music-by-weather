import os
import time
import pandas as pd
from .last_fm_tag import get_tracks_by_tag_range, get_track_info
from .genius_api import get_lyrics

def get_tracks_with_lyrics_by_tag(tag, start_page, end_page, max_tracks):
    tracks = get_tracks_by_tag_range(tag, start_page, end_page)
    results = []
    for i, track in enumerate(tracks[:max_tracks], 1):
        name = track.get("name")
        artist = track.get("artist", {}).get("name") if isinstance(track.get("artist"), dict) else track.get("artist")
        print(f"\n{i}. {name} – {artist}")

        # Get detailed info from Last.fm
        info = get_track_info(name, artist)
        album = info.get("album", {}).get("title", "N/A")
        playcount = info.get("playcount", "N/A")
        duration_ms = int(info.get("duration", 0))
        duration_min = round(duration_ms / 60000, 2) if duration_ms else "N/A"
        summary = info.get("wiki", {}).get("summary", "").split("<a")[0]
        track_url = track.get("url")

        # Get lyrics from Genius
        lyrics = get_lyrics(artist, name)
        time.sleep(0.5)  # Be nice to APIs

        # Collect all info
        results.append({
            "name": name,
            "artist": artist,
            "album": album,
            "playcount": playcount,
            "duration_min": duration_min,
            "summary": summary,
            "track_url": track_url,
            "lyrics": lyrics
        })

        # Print summary
        print(f"   Album: {album}")
        print(f"   Playcount: {playcount}")
        print(f"   Duration: {duration_min} min")
        print(f"   Track URL: {track_url}")
        if summary:
            print(f"   Description: {summary.strip()[:200]}...")
        print("   Lyrics preview:")
        if lyrics:
            print(lyrics[:300] + ("..." if len(lyrics) > 300 else ""))
        else:
            print("   No lyrics found.")
        print("-" * 40)
    return results

