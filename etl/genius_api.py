import os
import requests
import re
from bs4 import BeautifulSoup
from airflow.models import Variable

# DO NOT fetch Airflow Variables at the module level!
# Fetch them inside functions, so Airflow context is available.

def search_song_on_genius(artist, title):
    """Search Genius for a song and return the first result's URL."""
    GENIUS_API_TOKEN = Variable.get("GENIUS_ACCESS_TOKEN")
    print(f"🔍 Searching Genius for: {artist} – {title}")
    base_url = "https://api.genius.com"
    headers = {
        "Authorization": f"Bearer {GENIUS_API_TOKEN}"
    }
    search_url = f"{base_url}/search"
    params = {"q": f"{artist} {title}"}

    response = requests.get(search_url, params=params, headers=headers)
    data = response.json()
    print("Genius API raw response:", data)

    if "response" not in data or "hits" not in data["response"] or not data["response"]["hits"]:
        print("Genius API error or no hits:", data)
        return None  # or handle gracefully

    genius_url = data["response"]["hits"][0]["result"]["url"]
    print(f"🔗 Found Genius URL: {genius_url}")
    return genius_url


def scrape_genius_lyrics(genius_url):
    """Scrape lyrics from a Genius song page."""
    print(f"📄 Scraping lyrics from: {genius_url}")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/114.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Referer": "https://www.google.com/"
    }
    response = requests.get(genius_url, headers=headers)
    if response.status_code != 200:
        print("❌ Failed to fetch Genius page.")
        return None

    soup = BeautifulSoup(response.text, "html.parser")
    lyrics_divs = soup.find_all("div", class_=re.compile("^Lyrics__Container"))

    if not lyrics_divs:
        print("⚠️ Could not find lyrics on the page.")
        return None

    lyrics_lines = []
    for div in lyrics_divs:
        for br in div.find_all("br"):
            br.replace_with("\n")
        text = div.get_text(separator="\n").strip()
        if text and not text.lower().startswith("translations"):
            lyrics_lines.append(text)

    # Combine and clean up excessive line breaks
    raw_lyrics = "\n".join(lyrics_lines)

    # Remove multiple consecutive blank lines
    cleaned_lyrics = re.sub(r"\n\s*\n+", "\n\n", raw_lyrics).strip()

    print("🎤 Lyrics:\n")
    print(cleaned_lyrics)
    return cleaned_lyrics

def get_lyrics(artist, title):
    genius_url = search_song_on_genius(artist, title)
    if genius_url:
        return scrape_genius_lyrics(genius_url)
    return None

