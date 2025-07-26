# Airflow 메타데이터 DB에서 LASTFM_API_KEY 가져오기 위해 db.py 재사용
# from .db import get_postgres_credentials_from_airflow # 이 라인을
from .db import get_redshift_credentials_from_airflow # 이렇게 변경합니다.

# LASTFM_API_KEY와 LASTFM_API_URL을 db에서 가져오거나 직접 정의하는 방식은
# 프로젝트의 설정에 따라 달라질 수 있습니다.
# 예를 들어, Last.fm API 키는 환경 변수에서 가져오거나 직접 여기에 정의할 수 있습니다.
# 예시:
LASTFM_API_KEY = "YOUR_LASTFM_API_KEY" # 실제 Last.fm API 키로 변경
LASTFM_API_URL = "http://ws.audioscrobbler.com/2.0/"

FASTAPI_BASE_URL = "http://10.0.45.211:8000" # 당신의 FastAPI 백엔드 주소
FRONTEND_URL = "http://15.165.108.160:8501" # 당신의 Streamlit 프론트엔드 주소

IS_PROD = False
DOCS_URL = "/docs" if not IS_PROD else None # 프로덕션 환경에서는 docs를 비활성화하는 경우가 많습니다.


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