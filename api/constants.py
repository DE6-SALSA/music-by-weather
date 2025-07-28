import os

REDSHIFT_CONFIG = {
    "host": os.environ.get("REDSHIFT_HOST"),
    "port": os.environ.get("REDSHIFT_PORT"),
    "database": os.environ.get("REDSHIFT_DBNAME"),
    "user": os.environ.get("REDSHIFT_USER"),
    "password": os.environ.get("REDSHIFT_PASSWORD")
}

LASTFM_API_KEY = os.environ.get("LASTFM_API_KEY")
LASTFM_API_URL = "http://ws.audioscrobbler.com/2.0/"

WEATHER_TO_TAGS_MAP = {
    "Clear": [
        "happy", "love", "summer", "sunny", "upbeat", "pop", "dance", "fun",
        "pop punk", "twerk anthem", "teen pop", "happy dance", "love anthem",
        "party music", "catchy as fuck", "dance-pop", "pop rock", "pop-rap",
        "sunshine pop", "reggaeton", "dancehall", "summer hits", "banger",
        "samba", "party", "uplifting", "pop perfection", "disco pop",
        "danceable", "good vibes"
    ],
    "Cloudy": [
        "indie", "alternative", "mellow", "chill", "folk", "soft rock",
        "indie pop", "indie folk", "indie rock", "chillwave", "dream pop",
        "post-rock", "singer-songwriter", "jangle pop", "folk rock",
        "alternative dance", "twee pop", "chillout", "cloudy pop", "surf rock"
    ],
    "Rainy": [
        "sad song", "heartbreak", "ballad", "melancholic", "crying my eyes out",
        "tear-jerker", "bittersweet", "heartbreakingly beautiful", "sadcore",
        "sad girl", "songs to cry to", "breakup", "regret", "despondency",
        "longing", "yearning", "cryingggg"
    ],
    "Stormy": [
        "metal", "hardcore", "emo", "punk", "aggressive", "screamo", "deathcore",
        "death metal", "black metal", "heavy metal", "thrash metal",
        "grindcore", "nu-metal", "noise rock", "sludge metal", "hardcore punk",
        "dark plugg", "violent"
    ],
    "Snowy": [
        "christmas", "winter", "dreamy", "ethereal", "ambient pop", "dreamy pop",
        "snowy", "icy"
    ],
    "Windy": [
        "jazz", "instrumental", "smooth", "airy", "ambient", "jazz fusion",
        "smooth jazz", "ambient dub", "jazz rap", "acid jazz", "bossa nova",
        "instrumental hip hop", "lounge", "easy listening", "cinematic",
        "chill jazz", "chamber jazz", "piano jazz", "flute", "acoustic instrumental"
    ],
    "Hot": [
        "tropical house", "reggaeton", "baile funk", "dembow", "summer hits",
        "samba rock", "samba de raiz", "latin pop", "dancehall", "moombahton",
        "tropical", "caliente", "hot", "afrobeat", "afropiano"
    ],
    "Cold": [
        "dark pop", "coldwave", "gothic", "darkwave", "industrial", "icy",
        "dark ambient", "witch house", "blackgaze", "depressive black metal"
    ],
}
