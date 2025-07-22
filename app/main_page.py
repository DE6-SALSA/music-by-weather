import urllib.parse
import os
import streamlit as st
import pandas as pd
import requests
import animations
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(layout="wide")

FASTAPI_BASE_URL = os.environ.get("FASTAPI_BASE_URL", "http://127.0.0.1:8000")

# --- FastAPI에서 데이터를 가져오는 함수들 ---
@st.cache_data(ttl=3600)
def get_distinct_level1_from_api():
    try:
        response = requests.get(f"{FASTAPI_BASE_URL}/locations/level1")
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"FastAPI에서 시/도 목록을 가져오는 중 오류 발생: {e}. FastAPI 서버가 실행 중인지 확인해주세요.")
        return []

@st.cache_data(ttl=3600)
def get_distinct_level2_from_api(level1_name):
    if not level1_name:
        return []
    try:
        response = requests.get(f"{FASTAPI_BASE_URL}/locations/level2", params={"level1_name": level1_name})
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"FastAPI에서 시/군/구 목록을 가져오는 중 오류 발생: {e}")
        return []

@st.cache_data(ttl=3600)
def get_weather_data_from_api(level1_name, level2_name):
    if not level1_name or not level2_name:
        return {}
    try:
        encoded_level1 = urllib.parse.quote(level1_name)
        encoded_level2 = urllib.parse.quote(level2_name)
        response = requests.get(f"{FASTAPI_BASE_URL}/weather/current?level1={encoded_level1}&level2={encoded_level2}")
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"FastAPI에서 날씨 정보를 가져오는 중 오류 발생: {e}. 요청 URL: {response.url if 'response' in locals() else 'N/A'}")
        return {}

def get_chart_rank_from_api():
    if 'chart_rank_data' not in st.session_state:
        try:
            with st.spinner("차트 순위 가져오는 중..."):
                response = requests.get(f"{FASTAPI_BASE_URL}/chart_rank?limit=10")
                response.raise_for_status()
                st.session_state.chart_rank_data = response.json()
        except requests.exceptions.RequestException as e:
            st.error(f"FastAPI에서 차트 순위를 가져오는 중 오류 발생: {e}")
            st.session_state.chart_rank_data = []
    return st.session_state.chart_rank_data

@st.cache_data(ttl=300)
def get_weather_based_recommendations_from_api(location: str, sub_location: str, randomize: bool = False):
    try:
        encoded_location = urllib.parse.quote(location)
        encoded_sub_location = ""
        if sub_location:
            encoded_sub_location = urllib.parse.quote(sub_location)
        recommend_url = f"{FASTAPI_BASE_URL}/recommend/weather?location={encoded_location}&limit=10"
        if encoded_sub_location:
            recommend_url += f"&sub_location={encoded_sub_location}"
        if randomize:
            recommend_url += "&randomize=true"
        response = requests.get(recommend_url)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"FastAPI에서 날씨 기반 추천을 가져오는 중 오류 발생: {e}. 요청 URL: {response.url if 'response' in locals() else 'N/A'}")
        return []

@st.cache_data(ttl=300)
def search_music_from_api(query: str, randomize: bool = False):
    try:
        encoded_query = urllib.parse.quote(query)
        search_url = f"{FASTAPI_BASE_URL}/search/music?query={encoded_query}&limit=10"
        if randomize:
            search_url += "&randomize=true"
        response = requests.get(search_url)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"FastAPI에서 음악 검색 결과를 가져오는 중 오류 발생: {e}. 요청 URL: {response.url if 'response' in locals() else 'N/A'}")
        return []

@st.cache_data(ttl=300)
def get_lyrics_based_recommendations_from_api(query: str, randomize: bool = False):
    if not query:
        return []
    try:
        encoded_query = urllib.parse.quote(query)
        recommend_url = f"{FASTAPI_BASE_URL}/recommend/lyrics?query={encoded_query}&limit=10"
        if randomize:
            recommend_url += "&randomize=true"
        response = requests.get(recommend_url)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"FastAPI에서 가사 기반 추천을 가져오는 중 오류 발생: {e}. 요청 URL: {response.url if 'response' in locals() else 'N/A'}")
        return []

# 공통 CSS 오버라이드
def load_css(file_name):
    with open(file_name, "r", encoding='utf-8') as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

load_css("styles.css")

# --- 디버그: 날씨 강제 설정 (사이드바) ---
st.sidebar.markdown("## 🛠️ Debug")
debug_weather = st.sidebar.selectbox(
    "테스트용 날씨 입력",
    ["(API 사용)", "Clear", "Rainy", "Snowy", "Cloudy", "Windy", "Stormy", "Hot", "Cold"],
    index=0
)

# --- 비디오 매핑 ---
mapping = {
    "Clear": "https://cdn-icons-mp4.flaticon.com/512/17102/17102813.mp4",
    "Rainy": "https://cdn-icons-mp4.flaticon.com/512/17102/17102963.mp4",
    "Snowy": "https://cdn-icons-mp4.flaticon.com/512/17484/17484878.mp4",
    "Windy": "https://cdn-icons-mp4.flaticon.com/512/17102/17102829.mp4",
    "Cloudy": "https://cdn-icons-mp4.flaticon.com/512/17102/17102874.mp4",
    "Stormy": "https://cdn-icons-mp4.flaticon.com/512/17102/17102956.mp4",
    "Hot": "https://cdn-icons-mp4.flaticon.com/512/17103/17103056.mp4",
    "Cold": "https://cdn-icons-mp4.flaticon.com/512/17103/17103071.mp4"
}

# 초기 날씨 데이터 로드
if "selected_level1" not in st.session_state:
    st.session_state["selected_level1"] = "서울특별시"
if "selected_level2" not in st.session_state:
    st.session_state["selected_level2"] = "강남구"

weather_data_initial = get_weather_data_from_api(st.session_state["selected_level1"], st.session_state["selected_level2"])
current_weather_description_initial = weather_data_initial.get("description", "").capitalize()

# 디버그 override
if debug_weather != "(API 사용)":
    weather_text = debug_weather
else:
    weather_text = current_weather_description_initial if current_weather_description_initial in mapping else "Clear"

st.session_state["weather_text"] = weather_text
weather_video = mapping.get(weather_text, mapping["Clear"])

# --- 날씨 조건에 따른 제목 및 특정 p 태그 색상 결정 ---
header_text_color = "black"  # 기본값
if weather_text in ["Rainy", "Snowy", "Stormy", "Cold"]:
    header_text_color = "white"

# 이 색상을 chart_rank.py에서도 사용할 수 있도록 session_state에 저장
st.session_state["header_text_color_for_chart"] = header_text_color

# --- Streamlit 앱의 타이틀 ---
st.markdown(f"""
<h1 style='text-align: center; font-size: 3em; font-family: "Comic Sans MS", "Segoe UI Emoji", "Arial", sans-serif; color: {header_text_color}; text-shadow: 1px 1px 2px rgba(0,0,0,0.1);'>
Weatherify
</h1>
""", unsafe_allow_html=True)

# "날씨와 음악의 완벽한 조화" 색상 및 위치 동적 적용
st.markdown(f"""
<p style='text-align: center; font-family: "Comic Sans MS", "Segoe UI Emoji", "Arial", sans-serif; color: {header_text_color}; font-size: 1.1em; margin-bottom: 40px;'>날씨와 음악의 완벽한 조화 🌞🎶</p>
""", unsafe_allow_html=True)

# --- 전역 CSS 오버라이드 ---
st.markdown(f"""
<style>
    /* 전체 배경을 투명하게 설정 */
    [data-testid], [class*="css-"] {{ background: transparent !important; }}
    .stApp, body {{ background: transparent !important; }}

    /* 날씨에 따라 제목(h2~h6)만 동적으로 변경 (h1은 inline 스타일로 관리) */
    h2, h3, h4, h5, h6 {{
        font-family: 'Comic Sans MS', 'Segoe UI Emoji', 'Arial', sans-serif !important;
        color: {header_text_color} !important;
    }}

    /* 입력창 라벨 색상 */
    div[data-testid="stWidgetLabel"] > label {{
        font-family: 'Comic Sans MS', 'Segoe UI Emoji', 'Arial', sans-serif !important;
        color: {header_text_color} !important;
    }}

    /* 사이드바 내비게이션 링크는 항상 흰색 */
    div[data-testid="stSidebarNav"] a {{
        color: white !important;
    }}
    /* 사이드바 내비게이션 라벨 색상 (선택 안 된 페이지) */
    div[data-testid="stSidebarNav"] li > div {{
        color: white !important;
    }}
    /* 사이드바 내비게이션 선택된 페이지의 라벨 색상 */
    div[data-testid="stSidebarNav"] li > div[data-selected="true"] {{
        color: white !important;
    }}

    /* Streamlit selectbox 드롭다운 화살표 색상 */
    .stSelectbox > div > div > div > div svg {{ fill: black; }}

    /* main_page.py의 일반 st.button 스타일 (New, Search, 가사 검색 버튼) */
    .stButton > button {{
        font-family: 'Comic Sans MS', 'Segoe UI Emoji', 'Arial', sans-serif !important;
        border-color: black !important;
        background-color: white !important;
        color: black !important;
    }}
    .stButton > button:hover {{
        background-color: #e6e6e6 !important;
    }}

    /* main_page.py의 st.link_button 스타일 (아티스트/트랙 페이지 링크 버튼) */
    a[data-testid*="stLinkButton"] {{
        font-family: 'Comic Sans MS', 'Segoe UI Emoji', 'Arial', sans-serif !important;
        background-color: white !important;
        border-color: black !important;
        padding: 0.25rem 0.75rem;
        border-radius: 0.25rem;
        text-decoration: none;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        font-weight: 400;
        line-height: 1.6;
        text-align: center;
        white-space: nowrap;
        vertical-align: middle;
        user-select: none;
        transition: color .15s ease-in-out,background-color .15s ease-in-out,border-color .15s ease-in-out,box-shadow .15s ease-in-out;
    }}
    a[data-testid*="stLinkButton"]:hover {{
        background-color: #f0f2f6 !important;
    }}

    /* 날씨 박스 배경색 (항상 흰색 유지) */
    .weather-content {{
        background-color: white;
    }}
    /* 날씨 박스 안의 비디오 플레이스홀더 (애니메이션)도 투명하게 설정 */
    .weather-display video {{
        background: transparent !important;
    }}

    /* 음악 카드 내부 텍스트 색상 */
    .music-card p,
    .music-info-box .artist-name,
    .music-info-box .track-title,
    .music-tags-box .tags-text {{
        color: black !important;
    }}
</style>
""", unsafe_allow_html=True)

# --- Streamlit 앱 본문 ---
col_region_setting, col_weather_info, col_chart_rank = st.columns([1, 1, 2])

with col_region_setting:
    st.subheader("지역 설정")
    
    available_level1 = get_distinct_level1_from_api()
    if not available_level1:
        st.warning("시/도 목록을 가져올 수 없습니다. FastAPI 서버 상태를 확인해주세요.")
        available_level1 = ["데이터 없음"]
    
    default_level1_index = 0
    if "서울특별시" in available_level1:
        default_level1_index = available_level1.index("서울특별시")
    elif available_level1:
        default_level1_index = 0

    st.markdown(f"<div style='color: {header_text_color}; font-family: \"Comic Sans MS\", \"Segoe UI Emoji\", \"Arial\", sans-serif;'>도/시를 골라주세요.</div>", unsafe_allow_html=True)
    selected_level1 = st.selectbox("", available_level1, index=default_level1_index, key="level1_selector")
    st.session_state["selected_level1"] = selected_level1

    available_level2 = []
    if selected_level1 and selected_level1 != "데이터 없음":
        available_level2 = get_distinct_level2_from_api(selected_level1)
    
    if not available_level2:
        st.warning(f"'{selected_level1}'에 대한 시/군/구 목록을 가져올 수 없습니다. FastAPI 서버 상태를 확인해주세요.")
        available_level2 = ["데이터 없음"]

    default_level2_index = 0
    if selected_level1 == "서울특별시" and "강남구" in available_level2:
        default_level2_index = available_level2.index("강남구")
    elif available_level2:
        default_level2_index = 0
        
    st.markdown(f"<div style='color: {header_text_color}; font-family: \"Comic Sans MS\", \"Segoe UI Emoji\", \"Arial\", sans-serif;'>군/구를 골라주세요.</div>", unsafe_allow_html=True)
    selected_level2 = st.selectbox("", available_level2, index=default_level2_index, key="level2_selector")
    st.session_state["selected_level2"] = selected_level2

with col_weather_info:
    st.subheader("현재 날씨")

    weather_data = get_weather_data_from_api(selected_level1, selected_level2)
    current_weather_description = weather_data.get("description", "").capitalize()

    # 디버그 override
    if debug_weather != "(API 사용)":
        weather_data = {
            "description": debug_weather,
            "temperature": 25,
            "humidity": 50,
            "precipitation": 1.2,
            "wsd": 2.5
        }
    
    ani_map = {
        "Clear": animations.clear_html,
        "Rainy": animations.rainy_html,
        "Snowy": animations.snowy_html,
        "Cloudy": animations.cloudy_html,
        "Windy": animations.windy_html,
        "Stormy": animations.stormy_html,
        "Hot": animations.hot_html,
        "Cold": animations.cold_html,
    }
        
    st.markdown(ani_map[weather_text](), unsafe_allow_html=True)

    if weather_data and selected_level1 != "데이터 없음" and selected_level2 != "데이터 없음":
        temperature = weather_data.get('temperature', 'N/A')
        
        st.markdown(f"""
            <div class='weather-content' style='background-color: white;'>
                <h3 style='text-align: center; margin-bottom: 10px;'>{selected_level1} {selected_level2}</h3>
                <div class='weather-display'>
                    <video src="{weather_video}" autoplay loop muted style="width:100px; height:100px;"></video>
                    <span class='temperature'>{temperature:.1f}°C</span>
                </div>
                <p class='weather-description'>{weather_text}</p>
                <p class='weather-detail'>습도: {weather_data.get('humidity', 'N/A')}%</p>
                <p class='weather-detail'>강수량: {weather_data.get('precipitation', 'N/A')} mm</p>
                <p class='weather-detail'>풍속: {weather_data.get('wsd', 'N/A')} m/s</p>
            </div>
        """, unsafe_allow_html=True)
    else:
        st.info(f"날씨 정보를 가져올 수 없습니다. ({selected_level1} {selected_level2})")

with col_chart_rank:
    st.subheader("차트 순위")
    chart_items = get_chart_rank_from_api()
    if chart_items:
        df_chart = pd.DataFrame([{
            "순위": item['rank'], 
            "가수": item['artist'], 
            "제목": item['title'],
            "많이 나온 태그": ' '.join(item['tags'][:3]) if item.get('tags') else 'N/A'
        } for item in chart_items])
        st.dataframe(df_chart[['순위', '가수', '제목', '많이 나온 태그']], hide_index=True)
    else:
        st.info("차트 순위를 가져올 수 없습니다.")

st.markdown("---")

# --- 날씨 기반 음악 추천 섹션 ---
if 'refresh_key' not in st.session_state:
    st.session_state.refresh_key = 0

col_title, col_button = st.columns([10, 1])
with col_title:
    st.subheader("현재 날씨 기반 음악 추천")
with col_button:
    if st.button("New", key="refresh_recommendations"):
        st.session_state.refresh_key += 1
        st.cache_data.clear()
        st.rerun()

weather_recommendations = get_weather_based_recommendations_from_api(selected_level1, selected_level2, randomize=True)

if weather_recommendations:
    actual_music_recs = [rec for rec in weather_recommendations if "artist" in rec]
    if "message" in weather_recommendations and isinstance(weather_recommendations, list) and len(weather_recommendations) > 0 and "message" in weather_recommendations[0] and not actual_music_recs:
        st.info(weather_recommendations[0]["message"])
    elif actual_music_recs:
        for row in range(2):
            rec_cols = st.columns(5)
            start_idx = row * 5
            end_idx = min((row + 1) * 5, len(actual_music_recs))
            for i, rec in enumerate(actual_music_recs[start_idx:end_idx]):
                with rec_cols[i]:
                    html_content = f"""
                    <div class='music-card'>
                        <div class='image-wrapper'>
                            """
                    if rec.get("image_url") and rec["image_url"].strip():
                        html_content += f"""<img src="{rec['image_url']}" class="music-image">"""
                    else:
                        html_content += f"""<div class='no-image-placeholder'>No Image</div>"""
                    html_content += f"""
                        </div>
                        <div class='music-info-box'>
                            <p class='artist-name'>{rec['artist']}</p>
                            <p class='track-title'>{rec['title']}</p>
                        </div>
                        <div class='music-link-box'>
                            """
                    if rec.get("artist_url") and rec["artist_url"].strip():
                        html_content += f"""<a href='{rec['artist_url']}' target='_blank'>아티스트 페이지</a>"""
                    else:
                        html_content += f"""<span class='link-placeholder'>아티스트 페이지 없음</span>"""
                    html_content += f"""
                        </div>
                        <div class='music-link-box'>
                            """
                    if rec.get("track_url") and rec["track_url"].strip():
                        html_content += f"""<a href='{rec['track_url']}' target='_blank'>트랙 페이지</a>"""
                    else:
                        html_content += f"""<span class='link-placeholder'>트랙 페이지 없음</span>"""
                    html_content += f"""
                        </div>
                        <div class='music-tags-box'>
                            <p class='tags-text'>
                                {f"{' '.join(rec['tags'])}" if rec.get('tags') else "No Tags"}
                            </p>
                        </div>
                    </div>
                    """
                    st.markdown(html_content, unsafe_allow_html=True)  
else:
    st.info("현재 날씨에 맞는 추천 음악이 없습니다.")

st.markdown("---")

# --- 태그 검색 섹션 ---
if 'search_refresh_key' not in st.session_state:
    st.session_state.search_refresh_key = 0

if 'search_query' not in st.session_state:
    st.session_state.search_query = ""

col_search_title, col_new_button = st.columns([10, 1])
with col_search_title:
    st.subheader("태그로 음악 검색")
with col_new_button:
    if st.button("New", key="refresh_search"):
        st.session_state.search_refresh_key += 1
        st.cache_data.clear()
        st.rerun()

st.markdown(f"<div style='color: {header_text_color}; font-family: \"Comic Sans MS\", \"Segoe UI Emoji\", \"Arial\", sans-serif;'>검색 키워드를 입력하세요 (예: exciting, drive, BTS, love 등)</div>", unsafe_allow_html=True)
st.session_state.search_query = st.text_input("", value=st.session_state.search_query, key="music_search_input")

search_triggered = st.button("Search", key="search_button")

search_results = []
if search_triggered and st.session_state.search_query.strip():
    search_results = search_music_from_api(st.session_state.search_query.strip(), randomize=False)
elif st.session_state.search_refresh_key > 0 and st.session_state.search_query.strip():
    search_results = search_music_from_api(st.session_state.search_query.strip(), randomize=True)

if search_results:
    actual_search_recs = [rec for rec in search_results if "artist" in rec]
    if "message" in search_results and isinstance(search_results, list) and len(search_results) > 0 and "message" in search_results[0] and not actual_search_recs:
        st.info(search_results[0]["message"])
    elif actual_search_recs:
        for row in range(2):
            rec_cols = st.columns(5)
            start_idx = row * 5
            end_idx = min((row + 1) * 5, len(actual_search_recs))
            for i, rec in enumerate(actual_search_recs[start_idx:end_idx]):
                with rec_cols[i]:
                    html_content = f"""
                    <div class='music-card'>
                        <div class='image-wrapper'>
                            """
                    if rec.get("image_url") and rec["image_url"].strip():
                        html_content += f"""<img src="{rec['image_url']}" class="music-image">"""
                    else:
                        html_content += f"""<div class='no-image-placeholder'>No Image</div>"""
                    html_content += f"""
                        </div>
                        <div class='music-info-box'>
                            <p class='artist-name'>**{rec['artist']}**</p>
                            <p class='track-title'>*{rec['title']}*</p>
                        </div>
                        <div class='music-link-box'>
                            """
                    if rec.get("artist_url") and rec["artist_url"].strip():
                        html_content += f"""<a href='{rec['artist_url']}' target='_blank'>아티스트 페이지</a>"""
                    else:
                        html_content += f"""<span class='link-placeholder'>아티스트 페이지 없음</span>"""
                    html_content += f"""
                        </div>
                        <div class='music-link-box'>
                            """
                    if rec.get("track_url") and rec["track_url"].strip():
                        html_content += f"""<a href='{rec['track_url']}' target='_blank'>트랙 페이지</a>"""
                    else:
                        html_content += f"""<span class='link-placeholder'>트랙 페이지 없음</span>"""
                    html_content += f"""
                        </div>
                        <div class='music-tags-box'>
                            <p class='tags-text'>
                                {f"`{' '.join(rec['tags'])}`" if rec.get('tags') else "`No Tags`"}
                            </p>
                        </div>
                    </div>
                    """
                    st.markdown(html_content, unsafe_allow_html=True)  
else:
    if search_triggered and not st.session_state.search_query.strip():
        st.warning("검색어를 입력해주세요.")
    elif search_triggered:
        st.info(f"'{st.session_state.search_query}'에 대한 검색 결과를 찾을 수 없습니다.")

st.markdown("---")

# --- 가사 기반 음악 추천 섹션 ---
if 'lyrics_search_refresh_key' not in st.session_state:
    st.session_state.lyrics_search_refresh_key = 0

if 'lyrics_search_query' not in st.session_state:
    st.session_state.lyrics_search_query = ""

col_lyrics_title, col_lyrics_new_button = st.columns([10, 1])
with col_lyrics_title:
    st.subheader("가사로 음악 검색")
with col_lyrics_new_button:
    if st.button("New", key="refresh_lyrics_search"):
        st.session_state.lyrics_search_refresh_key += 1
        st.cache_data.clear()
        st.rerun()

st.markdown(f"<div style='color: {header_text_color}; font-family: \"Comic Sans MS\", \"Segoe UI Emoji\", \"Arial\", sans-serif;'>가사 키워드를 입력하세요 (예: love, breakup, summer 등)</div>", unsafe_allow_html=True)
st.session_state.lyrics_search_query = st.text_input("", value=st.session_state.lyrics_search_query, key="lyrics_search_input")

lyrics_search_triggered = st.button("가사 검색", key="lyrics_search_button")

lyrics_search_results = []
if lyrics_search_triggered and st.session_state.lyrics_search_query.strip():
    lyrics_search_results = get_lyrics_based_recommendations_from_api(st.session_state.lyrics_search_query.strip(), randomize=False)
elif st.session_state.lyrics_search_refresh_key > 0 and st.session_state.lyrics_search_query.strip():
    lyrics_search_results = get_lyrics_based_recommendations_from_api(st.session_state.lyrics_search_query.strip(), randomize=True)

if lyrics_search_results:
    actual_lyrics_recs = [rec for rec in lyrics_search_results if "artist" in rec]
    if "message" in lyrics_search_results and isinstance(lyrics_search_results, list) and len(lyrics_search_results) > 0 and "message" in lyrics_search_results[0] and not actual_lyrics_recs:
        st.info(lyrics_search_results[0]["message"])
    elif actual_lyrics_recs:
        for row in range(2):
            rec_cols = st.columns(5)
            start_idx = row * 5
            end_idx = min((row + 1) * 5, len(actual_lyrics_recs))
            for i, rec in enumerate(actual_lyrics_recs[start_idx:end_idx]):
                with rec_cols[i]:
                    html_content = f"""
                    <div class='music-card'>
                        <div class='image-wrapper'>
                            """
                    if rec.get("image_url") and rec["image_url"].strip():
                        html_content += f"""<img src="{rec['image_url']}" class="music-image">"""
                    else:
                        html_content += f"""<div class='no-image-placeholder'>No Image</div>"""
                    html_content += f"""
                        </div>
                        <div class='music-info-box'>
                            <p class='artist-name'>**{rec['artist']}**</p>
                            <p class='track-title'>*{rec['title']}*</p>
                        </div>
                        <div class='music-link-box'>
                            """
                    if rec.get("artist_url") and rec["artist_url"].strip():
                        html_content += f"""<a href='{rec['artist_url']}' target='_blank'>아티스트 페이지</a>"""
                    else:
                        html_content += f"""<span class='link-placeholder'>아티스트 페이지 없음</span>"""
                    html_content += f"""
                        </div>
                        <div class='music-link-box'>
                            """
                    if rec.get("track_url") and rec["track_url"].strip():
                        html_content += f"""<a href='{rec['track_url']}' target='_blank'>트랙 페이지</a>"""
                    else:
                        html_content += f"""<span class='link-placeholder'>트랙 페이지 없음</span>"""
                    html_content += f"""
                        </div>
                        <div class='music-tags-box'>
                            <p class='tags-text'>
                                {f"`{' '.join(rec['tags'])}`" if rec.get('tags') else "`No Tags`"}
                            </p>
                        </div>
                    </div>
                    """
                    st.markdown(html_content, unsafe_allow_html=True)  
else:
    if lyrics_search_triggered and not st.session_state.lyrics_search_query.strip():
        st.warning("가사 검색어를 입력해주세요.")
    elif lyrics_search_triggered:
        st.info(f"'{st.session_state.lyrics_search_query}'에 대한 검색 결과를 찾을 수 없습니다.")