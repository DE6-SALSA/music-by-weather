import urllib.parse
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

FASTAPI_BASE_URL = os.environ.get("FASTAPI_BASE_URL", "http://127.0.0.1:8000")

# --- CSS 스타일 로드 함수 ---
def load_css(file_name):
    with open(file_name, "r", encoding='utf-8') as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# CSS 파일 로드
load_css("styles.css")

# --- Streamlit 앱의 타이틀 ---
st.markdown("<h1>Weatherify</h1>", unsafe_allow_html=True)
st.markdown("<p>날씨와 음악의 완벽한 조화 🎶</p>", unsafe_allow_html=True)

# --- FastAPI에서 데이터를 가져오는 함수들 ---
@st.cache_data(ttl=3600) # 1시간 캐시 
def get_distinct_level1_from_api():
    try:
        response = requests.get(f"{FASTAPI_BASE_URL}/locations/level1")
        response.raise_for_status() 
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"FastAPI에서 시/도 목록을 가져오는 중 오류 발생: {e}. FastAPI 서버가 실행 중인지 확인해주세요.")
        return []

@st.cache_data(ttl=3600) # 1시간 캐시
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

@st.cache_data(ttl=3600) # 1시간 캐시
def get_weather_data_from_api(level1_name, level2_name):
    if not level1_name or not level2_name:
        return {}
    try:
        # 명시적으로 URL 인코딩 적용
        encoded_level1 = urllib.parse.quote(level1_name)
        encoded_level2 = urllib.parse.quote(level2_name)
        
        # requests.get의 params 대신, URL에 직접 인코딩된 파라미터를 포함
        response = requests.get(f"{FASTAPI_BASE_URL}/weather/current?level1={encoded_level1}&level2={encoded_level2}")
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"FastAPI에서 날씨 정보를 가져오는 중 오류 발생: {e}. 요청 URL: {response.url if 'response' in locals() else 'N/A'}")
        return {}

def get_chart_rank_from_api():
    # 세션 상태에 'chart_rank_data'가 없거나, 강제로 갱신해야 할 때만 API 호출
    if 'chart_rank_data' not in st.session_state:
        try:
            with st.spinner("차트 순위 가져오는 중..."): # 로딩 스피너 추가
                response = requests.get(f"{FASTAPI_BASE_URL}/chart_rank")
                response.raise_for_status()
                st.session_state.chart_rank_data = response.json()
        except requests.exceptions.RequestException as e:
            st.error(f"FastAPI에서 차트 순위를 가져오는 중 오류 발생: {e}")
            st.session_state.chart_rank_data = [] # 오류 시 빈 리스트
    return st.session_state.chart_rank_data

@st.cache_data(ttl=300) # 5분 캐시
def get_weather_based_recommendations_from_api(location: str, sub_location: str):
    try:
        # 명시적으로 URL 인코딩 적용
        encoded_location = urllib.parse.quote(location)
        encoded_sub_location = ""
        if sub_location:
            encoded_sub_location = urllib.parse.quote(sub_location)
        
        # URL에 직접 인코딩된 파라미터를 포함
        recommend_url = f"{FASTAPI_BASE_URL}/recommend/weather?location={encoded_location}"
        if encoded_sub_location:
            recommend_url += f"&sub_location={encoded_sub_location}"

        response = requests.get(recommend_url)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"FastAPI에서 날씨 기반 추천을 가져오는 중 오류 발생: {e}. 요청 URL: {response.url if 'response' in locals() else 'N/A'}")
        return []

@st.cache_data(ttl=300) # 5분 캐시
def search_music_from_api(query: str):
    try:
        encoded_query = urllib.parse.quote(query)
        response = requests.get(f"{FASTAPI_BASE_URL}/search/music?query={encoded_query}")
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"FastAPI에서 음악 검색 결과를 가져오는 중 오류 발생: {e}. 요청 URL: {response.url if 'response' in locals() else 'N/A'}")
        return []

# --- Streamlit 앱 본문 ---
# 첫 번째 단락: 위치 설정, 날씨 정보, CHART_RANK를 3등분하여 배치 (비율 조정)
col_region_setting, col_weather_info, col_chart_rank = st.columns([1, 1, 2])

with col_region_setting:
    st.subheader("지역 설정")
    
    # 시/도 목록 가져오기
    available_level1 = get_distinct_level1_from_api()
    if not available_level1:
        st.warning("시/도 목록을 가져올 수 없습니다. FastAPI 서버 상태를 확인해주세요.")
        available_level1 = ["데이터 없음"]
    
    default_level1_index = 0
    if "서울특별시" in available_level1:
        default_level1_index = available_level1.index("서울특별시")
    elif available_level1:
        default_level1_index = 0

    selected_level1 = st.selectbox("도/시를 골라주세요.", available_level1, index=default_level1_index, key="level1_selector")

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
        
    selected_level2 = st.selectbox("군/구를 골라주세요.", available_level2, index=default_level2_index, key="level2_selector")

with col_weather_info:
    st.subheader("현재 날씨")

    weather_data = get_weather_data_from_api(selected_level1, selected_level2)
    current_weather_description = weather_data.get("description", "").lower() 

    # 날씨 조건에 따라 배경색과 아이콘 결정
    weather_box_background_color = "#FFFFFF" # 기본 흰색
    weather_icon_image = "https://cdn-icons-png.flaticon.com/512/1779/1779940.png" # 기본 아이콘
    weather_text = weather_data.get("description", "N/A").capitalize() # 기본 날씨 텍스트

    # 날씨 조건별 색상 및 아이콘 매핑
    if "맑음" in current_weather_description or "Clear" in current_weather_description:
        weather_box_background_color = "#FFECB3" 
        weather_icon_image = "https://cdn-icons-png.flaticon.com/512/861/861053.png" 
        weather_text = "Sunny"
        text_color_for_weather_box = "#795548" 
    elif "비" in current_weather_description or "Rainy" in current_weather_description:
        weather_box_background_color = "#263238" 
        weather_icon_image = "https://cdn-icons-png.flaticon.com/512/3353/3353982.png" 
        weather_text = "Rainy"
        text_color_for_weather_box = "#CFD8DC" 
    elif "눈" in current_weather_description or "Snowy" in current_weather_description:
        weather_box_background_color = "#E0F2F7"
        weather_icon_image = "https://cdn-icons-png.flaticon.com/512/2315/2315309.png" 
        weather_text = "Snowy"
        text_color_for_weather_box = "#424242" 
    elif "흐림" in current_weather_description or "Cloudy" in current_weather_description:
        weather_box_background_color = "#CFD8DC" 
        weather_icon_image = "https://cdn-icons-png.flaticon.com/512/1163/1163624.png"
        weather_text = "Cloudy"
        text_color_for_weather_box = "#424242" 
    elif "번개" in current_weather_description or "Stormy" in current_weather_description:
        weather_box_background_color = "#455A64" 
        weather_icon_image = "https://cdn-icons-png.flaticon.com/512/1146/1146860.png" 
        weather_text = "Stormy"
        text_color_for_weather_box = "#CFD8DC" 
    elif "폭염" in current_weather_description or "Hot" in current_weather_description:
        weather_box_background_color = "#FF7043" 
        weather_icon_image = "https://cdn-icons-png.flaticon.com/512/1210/1210419.png" 
        weather_text = "Hot"
        text_color_for_weather_box = "#FFFFFF" 
    elif "한파" in current_weather_description or "Cold" in current_weather_description:
        weather_box_background_color = "#BBDEFB" 
        weather_icon_image = "https://cdn-icons-png.flaticon.com/512/6120/6120300.png" 
        weather_text = "Cold"
        text_color_for_weather_box = "#424242" 
    else: 
        weather_icon_image = "https://cdn-icons-png.flaticon.com/512/1779/1779940.png" 
        text_color_for_weather_box = "#424242"  

    if weather_data and selected_level1 != "데이터 없음" and selected_level2 != "데이터 없음":
        temperature = weather_data.get('temperature', 'N/A')
        
        st.markdown(f"""
            <div class='weather-content' style='background-color: {weather_box_background_color};'>
                <h3 style='color: #424242; text-align: center; margin-bottom: 10px;'>{selected_level1} {selected_level2}</h3>
                <div class='weather-display'>
                    <img src="{weather_icon_image}" alt="{weather_text}" class='weather-icon'>
                    <span class='temperature' style='color: #424242;'>{temperature}°C</span>
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
# 세션 상태 초기화
if 'refresh_key' not in st.session_state:
    st.session_state.refresh_key = str(datetime.now())

# 제목과 버튼을 같은 줄에 표시
col_title, col_button = st.columns([10, 1])
with col_title:
    st.subheader("현재 날씨 기반 음악 추천")
with col_button:
    if st.button("New", key="refresh_recommendations"):
        # 버튼 클릭 시 refresh_key 갱신
        st.session_state.refresh_key = str(datetime.now())

# 캐시 없이 API 호출
weather_recommendations = get_weather_based_recommendations_from_api(selected_level1, selected_level2)

if weather_recommendations:
    # 'message' 키가 있는 경우와 없는 경우를 분리하여 처리
    # 실제 음악 추천 데이터가 담긴 리스트를 가져옵니다.
    actual_music_recs = [rec for rec in weather_recommendations if "artist" in rec]

    if "message" in weather_recommendations[0] and not actual_music_recs:
        # 메시지만 있고 실제 음악 추천이 없는 경우
        st.info(weather_recommendations[0]["message"])
    elif actual_music_recs:
        # 실제 음악 추천이 있는 경우
        # 5칸씩 2줄로 표시 (최대 10개 항목)
        for row in range(2):  # 2줄
            rec_cols = st.columns(5)  # 5칸
            start_idx = row * 5
            end_idx = min((row + 1) * 5, len(actual_music_recs))
            for i, rec in enumerate(actual_music_recs[start_idx:end_idx]):
                with rec_cols[i]:
                    # 모든 HTML을 하나의 변수로 구성
                    html_content = f"""
                    <div class='music-card'>
                        <div class='image-wrapper'>
                            """
                    if rec.get("image_url") and rec["image_url"].strip():
                        html_content += f"""<img src="{rec["image_url"]}" class="music-image">"""
                    else:
                        html_content += f"""<div class='no-image-placeholder'>No Image</div>"""
                    
                    html_content += f"""
                        </div>
                        <div class='music-info-box'>
                            <p class='artist-name'>**{rec['artist']}**</p>
                            <p class='track-title'>*{rec['title']}*</p>
                        </div>
                    """

                    # 아티스트 페이지 링크
                    html_content += f"""<div class='music-link-box'>"""
                    if rec.get("artist_url") and rec["artist_url"].strip():
                        html_content += f"""<a href='{rec['artist_url']}' target='_blank'>아티스트 페이지</a>"""
                    else:
                        html_content += f"""<span class='link-placeholder'>아티тисти 페이지 없음</span>"""
                    html_content += f"""</div>"""

                    # 트랙 페이지 링크
                    html_content += f"""<div class='music-link-box'>"""
                    if rec.get("track_url") and rec["track_url"].strip():
                        html_content += f"""<a href='{rec['track_url']}' target='_blank'>트랙 페이지</a>"""
                    else:
                        html_content += f"""<span class='link-placeholder'>트랙 페이지 없음</span>"""
                    html_content += f"""</div>"""

                    # 태그
                    html_content += f"""
                        <div class='music-tags-box'>
                            <p class='tags-text'>
                                {f"`{' '.join(rec['tags'])}`" if rec.get('tags') else "`No Tags`"}
                            </p>
                        </div>
                    """
                    html_content += f"""</div>""" # music-card 닫기

                    st.markdown(html_content, unsafe_allow_html=True)
else:
    st.info("현재 날씨에 맞는 추천 음악이 없습니다.")

st.markdown("---")

# --- 태그 검색 섹션 ---
if 'search_refresh_key' not in st.session_state:
    st.session_state.search_refresh_key = str(datetime.now())

if 'search_query' not in st.session_state:
    st.session_state.search_query = ""

col_search_title, col_new_button = st.columns([10, 1])
with col_search_title:
    st.subheader("태그로 음악 검색")
with col_new_button:
    if st.button("New", key="refresh_search"):
        st.session_state.search_refresh_key = str(datetime.now())
        # 'New' 버튼 클릭 시 검색 쿼리 초기화 (선택 사항)
        # st.session_state.search_query = "" 

# --- 키워드 입력창 & Search 버튼 ---
st.session_state.search_query = st.text_input(
    "검색 키워드를 입력하세요 (예: exciting, drive, BTS, love 등)",
    value=st.session_state.search_query,
    key="music_search_input"
)

search_triggered = st.button("Search", key="search_button")

# NameError 해결: search_results를 항상 초기화
search_results = [] 
if search_triggered and st.session_state.search_query.strip():
    search_results = search_music_from_api(st.session_state.search_query.strip())
elif st.session_state.search_refresh_key and st.session_state.search_query.strip():
    # 'New' 버튼을 누르거나 새로고침 시에도 기존 검색어가 있다면 다시 검색
    search_results = search_music_from_api(st.session_state.search_query.strip())

if search_results:
    # 'message' 키가 있는 경우와 없는 경우를 분리하여 처리
    actual_search_recs = [rec for rec in search_results if "artist" in rec]

    if "message" in search_results[0] and not actual_search_recs:
        st.info(search_results[0]["message"])
    elif actual_search_recs:
        for row in range(2):
            rec_cols = st.columns(5)
            start_idx = row * 5
            end_idx = min((row + 1) * 5, len(actual_search_recs))
            for i, rec in enumerate(actual_search_recs[start_idx:end_idx]):
                with rec_cols[i]:
                    # 모든 HTML을 하나의 변수로 구성 (날씨 추천 섹션과 동일하게)
                        html_content = f"""
                        <div class='music-card'>
                            <div class='image-wrapper'>
                                """
                        if rec.get("image_url") and rec["image_url"].strip():
                            html_content += f"""<img src="{rec["image_url"]}" class="music-image">"""
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
    elif search_triggered: # 검색 버튼을 눌렀는데 결과가 없거나, 검색어가 있는데 결과가 없는 경우
        st.info(f"'{st.session_state.search_query}'에 대한 검색 결과를 찾을 수 없습니다.")
    # 초기 로드 시에는 메시지를 표시하지 않음 (search_triggered가 False일 때)

st.markdown("---")

st.subheader("가사 기반 음악 추천")