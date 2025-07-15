import os
import streamlit as st
import pandas as pd
import requests
from datetime import datetime
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv() 

# 페이지 설정: 와이드 레이아웃으로 설정하여 더 넓은 화면 사용
st.set_page_config(layout="wide")

# FastAPI 서버의 기본 URL (FastAPI가 실행되는 주소)
# 로컬 개발 시 기본값은 http://127.0.0.1:8000
# 배포 환경에서는 FastAPI 서버의 실제 도메인으로 변경 예정.
FASTAPI_BASE_URL = os.environ.get("FASTAPI_BASE_URL", "http://127.0.0.1:8000")

# --- Streamlit 앱의 타이틀 ---
st.title("MUSIC & WEATHER RECOMMENDATION SERVICE") # 웹사이트 이름

# --- FastAPI에서 데이터를 가져오는 함수들 ---
# @st.cache_data 데코레이터를 사용하여 API 호출 결과를 캐싱, 성능 향상
# ttl(Time To Live)을 설정하여 데이터가 얼마나 오랫동안 캐시될지 지정
@st.cache_data(ttl=3600) # 1시간 캐시 
def get_distinct_level1_from_api():
    """FastAPI에서 시/도(level1) 목록을 가져옵니다."""
    try:
        response = requests.get(f"{FASTAPI_BASE_URL}/locations/level1")
        response.raise_for_status() # HTTP 에러 발생 시 예외 발생
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"FastAPI에서 시/도 목록을 가져오는 중 오류 발생: {e}. FastAPI 서버가 실행 중인지 확인해주세요.")
        return []

@st.cache_data(ttl=3600) # 1시간 캐시
def get_distinct_level2_from_api(level1_name):
    """FastAPI에서 선택된 시/도에 대한 시/군/구(level2) 목록을 가져옵니다."""
    if not level1_name:
        return []
    try:
        response = requests.get(f"{FASTAPI_BASE_URL}/locations/level2", params={"level1_name": level1_name})
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"FastAPI에서 시/군/구 목록을 가져오는 중 오류 발생: {e}")
        return []

@st.cache_data(ttl=3600) # 1시간 캐시
def get_weather_data_from_api(level1_name, level2_name):
    """FastAPI에서 특정 지역의 날씨 정보를 가져옵니다."""
    if not level1_name or not level2_name:
        return {}
    try:
        response = requests.get(f"{FASTAPI_BASE_URL}/weather/current", params={"level1": level1_name, "level2": level2_name})
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"FastAPI에서 날씨 정보를 가져오는 중 오류 발생: {e}")
        return {}

@st.cache_data(ttl=3600) # 1시간 캐시
def get_recommendations_from_api():
    """FastAPI에서 추천 음악 정보를 가져옵니다."""
    try:
        response = requests.get(f"{FASTAPI_BASE_URL}/recommendations")
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"FastAPI에서 추천 앨범 정보를 가져오는 중 오류 발생: {e}")
        return []

@st.cache_data(ttl=60) # 1분 캐시 (차트 순위는 상대적으로 자주 변동될 수 있음)
def get_chart_rank_from_api():
    """FastAPI에서 차트 순위를 가져옵니다."""
    try:
        response = requests.get(f"{FASTAPI_BASE_URL}/chart_rank")
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"FastAPI에서 차트 순위를 가져오는 중 오류 발생: {e}")
        return []

@st.cache_data(ttl=300) # 5분 캐시
def get_weather_based_recommendations_from_api(location: str, sub_location: str):
    """FastAPI에서 날씨 기반 음악 추천을 가져옵니다."""
    try:
        params = {"location": location}
        if sub_location:
            params["sub_location"] = sub_location
        response = requests.get(f"{FASTAPI_BASE_URL}/recommend/weather", params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"FastAPI에서 날씨 기반 추천을 가져오는 중 오류 발생: {e}")
        return []

@st.cache_data(ttl=300) # 5분 캐시
def search_music_from_api(query: str):
    """FastAPI에서 음악 검색 결과를 가져옵니다."""
    try:
        response = requests.get(f"{FASTAPI_BASE_URL}/search/music", params={"query": query})
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"FastAPI에서 음악 검색 결과를 가져오는 중 오류 발생: {e}")
        return []

# --- CSS 스타일 정의 (박스 효과를 위한) ---
BOX_STYLE = """
    border: 1px solid #e0e0e0;
    border-radius: 8px;
    padding: 20px;
    margin-bottom: 20px;
    box-shadow: 2px 2px 5px rgba(0,0,0,0.1);
    background-color: #ffffff;
"""

RECOMMENDATION_BOX_STYLE = """
    border: 1px solid #f0f0f0;
    border-radius: 5px;
    padding: 10px;
    margin: 5px; /* 추천 항목 간 간격 */
    box-shadow: 1px 1px 3px rgba(0,0,0,0.05);
    background-color: #fcfcfc;
    text-align: center;
"""

MUSIC_CARD_STYLE = """
    border: 1px solid #ddd;
    border-radius: 8px;
    padding: 15px;
    margin-bottom: 15px;
    box-shadow: 0 2px 5px rgba(0,0,0,0.1);
    background-color: #f9f9f9;
    text-align: center;
"""

# --- Streamlit 앱 본문 ---

# 첫 번째 단락: 위치 설정, 날씨 정보, CHART_RANK를 3등분하여 배치
col_region_setting, col_weather_info, col_chart_rank = st.columns(3)

with col_region_setting:
    st.markdown(f"<div style='{BOX_STYLE}'>", unsafe_allow_html=True)
    st.subheader("REGION SETTING")
    
    # 시/도 목록 가져오기
    available_level1 = get_distinct_level1_from_api()
    if not available_level1:
        st.warning("시/도 목록을 가져올 수 없습니다. FastAPI 서버 상태를 확인해주세요.")
        available_level1 = ["데이터 없음"]
    
    # 기본 선택값 설정: 서울특별시가 있다면 서울특별시, 없다면 첫 번째 항목
    default_level1_index = 0
    if "서울특별시" in available_level1:
        default_level1_index = available_level1.index("서울특별시")
    elif available_level1:
        default_level1_index = 0

    selected_level1 = st.selectbox("Select Province/City", available_level1, index=default_level1_index, key="level1_selector")

    # 시/군/구 목록 가져오기
    available_level2 = []
    if selected_level1 and selected_level1 != "데이터 없음":
        available_level2 = get_distinct_level2_from_api(selected_level1)
    
    if not available_level2:
        st.warning(f"'{selected_level1}'에 대한 시/군/구 목록을 가져올 수 없습니다. FastAPI 서버 상태를 확인해주세요.")
        available_level2 = ["데이터 없음"] # 사용자에게 표시할 대체 텍스트

    # 기본 선택값 설정: 강남구 있다면 강남구, 없다면 첫 번째 항목
    default_level2_index = 0
    if selected_level1 == "서울특별시" and "강남구" in available_level2:
        default_level2_index = available_level2.index("강남구")
    elif available_level2:
        default_level2_index = 0
        
    selected_level2 = st.selectbox("Select City/District", available_level2, index=default_level2_index, key="level2_selector")

    st.markdown("</div>", unsafe_allow_html=True)

with col_weather_info:
    st.markdown(f"<div style='{BOX_STYLE}'>", unsafe_allow_html=True)
    st.subheader(f"CURRENT WEATHER IN {selected_level1} {selected_level2}")
    
    # 선택된 지역의 날씨 정보 가져오기
    weather_data = get_weather_data_from_api(selected_level1, selected_level2)

    if weather_data and selected_level1 != "데이터 없음" and selected_level2 != "데이터 없음":
        st.write("Current Weather")
        # 날씨 조건에 따른 이모지 설정
        weather_icon = "☀️"
        description = weather_data.get("description", "").lower()
        if "Rainy" in description or "비" in description:
            weather_icon = "🌧️"
        elif "Cloudy" in description or "흐림" in description:
            weather_icon = "☁️"
        elif "Hot" in description or "더움" in description:
            weather_icon = "🔥"
        elif "Clear" in description or "맑음" in description:
            weather_icon = "☀️"
        elif "Snowy" in description or "눈" in description:
            weather_icon = "❄️"
        elif "Stormy" in description or "천둥번개" in description:
            weather_icon = "⚡"
        
        st.markdown(f"**TEMP:** {weather_data.get('temp', 'N/A')}°C {weather_icon}")
        st.markdown(f"**HUMIDITY:** {weather_data.get('humidity', 'N/A')}%")
        st.markdown(f"**PRECIP:** {weather_data.get('precipitation', 'N/A')} mm")
        st.markdown(f"**Description:** {weather_data.get('description', 'N/A').capitalize()}")
        st.markdown(f"**Pty (강수형태):** {weather_data.get('pty', 'N/A')}")
        st.markdown(f"**Wsd (풍속):** {weather_data.get('wsd', 'N/A')} m/s")
        st.markdown(f"**Sky (하늘상태):** {weather_data.get('sky', 'N/A')}")
    else:
        st.info(f"날씨 정보를 가져올 수 없습니다. ({selected_level1} {selected_level2})")
    st.markdown("</div>", unsafe_allow_html=True)


with col_chart_rank:
    st.markdown(f"<div style='{BOX_STYLE}'>", unsafe_allow_html=True)
    st.subheader("CHART RANK")
    chart_items = get_chart_rank_from_api() # FastAPI에서 차트 순위 가져오기
    if chart_items:
        # 데이터프레임으로 변환하여 테이블 형태로 표시
        df_chart = pd.DataFrame([{"RANK": item['rank'], "ARTIST": item['artist'], "TITLE": item['title']} for item in chart_items])
        st.dataframe(df_chart[['RANK', 'ARTIST', 'TITLE']], hide_index=True) 
    else:
        st.info("차트 순위를 가져올 수 없습니다.")
    st.markdown("</div>", unsafe_allow_html=True)

st.markdown("---") # 구분선

# --- 날씨 기반 음악 추천 섹션 ---
st.header("MUSIC RECOMMENDATIONS BASED ON CURRENT WEATHER")
weather_recommendations = get_weather_based_recommendations_from_api(selected_level1, selected_level2)

if weather_recommendations:
    # 첫 번째 항목이 메시지일 경우 처리 (FastAPI에서 메시지를 함께 반환할 때)
    if weather_recommendations and "message" in weather_recommendations[0]:
        st.info(weather_recommendations[0]["message"])
        # 메시지 이후에 실제 음악 추천이 있다면 그것도 표시
        actual_music_recs = [rec for rec in weather_recommendations if "artist" in rec]
        if actual_music_recs:
            rec_cols = st.columns(5) # 5개 열로 분할
            for i, rec in enumerate(actual_music_recs):
                with rec_cols[i % 5]: # 각 열에 순서대로 배치
                    st.markdown(f"<div style='{MUSIC_CARD_STYLE}'>", unsafe_allow_html=True)
                    if rec.get("image_url"):
                        st.image(rec["image_url"], width=100)
                    else:
                        st.write("🖼️ No Image")
                    st.markdown(f"**{rec['artist']}**")
                    st.markdown(f"*{rec['title']}*")
                    if rec.get('tags'):
                        st.markdown(f"<small>`{' '.join(rec['tags'])}`</small>", unsafe_allow_html=True)
                    else:
                        st.markdown("<small>`No Tags`</small>", unsafe_allow_html=True)
                    st.markdown("</div>", unsafe_allow_html=True)
    else: # 메시지 없이 바로 음악 추천만 있을 경우
        rec_cols = st.columns(5)
        for i, rec in enumerate(weather_recommendations):
            with rec_cols[i % 5]:
                st.markdown(f"<div style='{MUSIC_CARD_STYLE}'>", unsafe_allow_html=True)
                if rec.get("image_url"):
                    st.image(rec["image_url"], width=100)
                else:
                    st.write("🖼️ No Image")
                st.markdown(f"**{rec['artist']}**")
                st.markdown(f"*{rec['title']}*")
                if rec.get('tags'):
                    st.markdown(f"<small>`{' '.join(rec['tags'])}`</small>", unsafe_allow_html=True)
                else:
                    st.markdown("<small>`No Tags`</small>", unsafe_allow_html=True)
                st.markdown("</div>", unsafe_allow_html=True)
else:
    st.info("현재 날씨에 맞는 추천 음악이 없습니다.")

st.markdown("---")

# --- 태그 검색 섹션 ---
st.header("SEARCH MUSIC BY TAGS")
search_query = st.text_input("Enter search keywords (e.g., exciting, drive, BTS, love, etc.)", key="music_search_input")

if st.button("Search Music", key="search_button") and search_query:
    search_results = search_music_from_api(search_query) # FastAPI 검색 API 호출
    if search_results:
        search_cols = st.columns(5)
        for i, music in enumerate(search_results):
            with search_cols[i % 5]:
                st.markdown(f"<div style='{MUSIC_CARD_STYLE}'>", unsafe_allow_html=True)
                if music.get("image_url"):
                    st.image(music["image_url"], width=100)
                else:
                    st.write("🖼️ No Image")
                st.markdown(f"**{music['artist']}**")
                st.markdown(f"*{music['title']}*")
                if music.get('tags'):
                    st.markdown(f"<small>`{' '.join(music['tags'])}`</small>", unsafe_allow_html=True)
                else:
                    st.markdown("<small>`No Tags`</small>", unsafe_allow_html=True)
                st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.info(f"'{search_query}'에 대한 검색 결과를 찾을 수 없습니다.")
elif st.button("Search Music", key="search_button_no_query") and not search_query:
    st.warning("검색어를 입력해주세요.")


st.markdown("---")

# --- RECOMMENDATIONS 섹션 (이전의 recommendations_data 활용) ---
st.header("OUR SPECIAL RECOMMENDATIONS")
general_recommendations = get_recommendations_from_api() # FastAPI에서 추천 앨범 정보 가져오기

if general_recommendations:
    rec_cols = st.columns(4) # 4개 열로 분할
    for i, rec in enumerate(general_recommendations):
        with rec_cols[(i % 4)]: # 각 열에 순서대로 배치
            st.markdown(f"<div style='{RECOMMENDATION_BOX_STYLE}'>", unsafe_allow_html=True)
            if rec.get("image_url"):
                st.image(rec["image_url"], width=100)
            else:
                st.write("🖼️ No Image")

            st.markdown(f"**{rec['artist']}**")
            st.markdown(f"*{rec['album']}* {rec.get('by', '')}")
            
            if rec.get('tags'):
                st.markdown(f"<small>`{' '.join(rec['tags'])}`</small>", unsafe_allow_html=True)
            else:
                st.markdown("<small>`No Tags`</small>", unsafe_allow_html=True)
            
            st.markdown("❤️", unsafe_allow_html=True) # 좋아요 아이콘 (기능 없음)
            st.markdown("</div>", unsafe_allow_html=True)
else:
    st.info("특별 추천 앨범 정보가 없습니다.")

st.caption(f"Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")