from __future__ import annotations
import os
from datetime import datetime
import streamlit as st
import pandas as pd
from dotenv import load_dotenv

from lib import api, theme, ui
 
load_dotenv()

st.set_page_config(layout="wide")

# ---------------- Session defaults -----------------
if "selected_level1" not in st.session_state:
    st.session_state.selected_level1 = "서울특별시"
if "selected_level2" not in st.session_state:
    st.session_state.selected_level2 = "강남구"
if "refresh_key" not in st.session_state:
    st.session_state.refresh_key = 0
if "search_refresh_key" not in st.session_state:
    st.session_state.search_refresh_key = 0
if "lyrics_search_refresh_key" not in st.session_state:
    st.session_state.lyrics_search_refresh_key = 0
if "search_query" not in st.session_state:
    st.session_state.search_query = ""
if "lyrics_search_query" not in st.session_state:
    st.session_state.lyrics_search_query = ""

# ---------------- Debug sidebar ---------------------
st.sidebar.markdown("## 🛠️ Debug")
debug_weather = st.sidebar.selectbox(
    "테스트용 날씨 입력",
    ["(API 사용)", "Clear", "Rainy", "Snowy", "Cloudy", "Windy", "Stormy", "Hot", "Cold"],
    index=0,
)

# ---------------- Load CSS --------------------------
ASSET_DIR = os.path.join(os.path.dirname(__file__), "assets")
CSS_PATH = os.path.join(ASSET_DIR, "styles.css")
if os.path.exists(CSS_PATH):
    theme.load_css(CSS_PATH)

# ---------------- Weather fetch ---------------------
weather_data_initial = api.get_weather(
    st.session_state.selected_level1, st.session_state.selected_level2
)
current_weather_description_initial = weather_data_initial.get("description", "").capitalize()

if debug_weather != "(API 사용)":
    weather_text = debug_weather
else:
    weather_text = (
        current_weather_description_initial
        if current_weather_description_initial in theme.WEATHER_VIDEO
        else "Clear"
    )

st.session_state.weather_text = weather_text
weather_video = theme.WEATHER_VIDEO.get(weather_text, theme.WEATHER_VIDEO["Clear"])

header_text_color = theme.header_color(weather_text)
st.session_state.header_text_color_for_chart = header_text_color

# ---------------- Title / Subtitle ------------------
st.markdown(
    f"""
<h1 style='text-align: center; font-size: 3em; font-family: "Comic Sans MS", "Segoe UI Emoji", "Arial", sans-serif; color: {header_text_color}; text-shadow: 1px 1px 2px rgba(0,0,0,0.1);'>
Weatherify
</h1>
<p style='text-align: center; font-family: "Comic Sans MS", "Segoe UI Emoji", "Arial", sans-serif; color: {header_text_color}; font-size: 1.1em; margin-bottom: 40px;'>날씨와 음악의 완벽한 조화 🌞🎶</p>
""",
    unsafe_allow_html=True,
)

theme.inject_global_css(header_text_color)

# ---------------- Body columns ----------------------
col_region_setting, col_weather_info, col_chart_rank = st.columns([1, 1, 2])

with col_region_setting:
    st.subheader("지역 설정")

    def label_html(text: str) -> str:
        return (
            f"<div style=\"color:{header_text_color}; "
            "font-family:'Comic Sans MS','Segoe UI Emoji','Arial',sans-serif;\">"
            f"{text}</div>"
        )

    available_level1 = api.get_level1_list() or ["데이터 없음"]
    default_level1_index = available_level1.index("서울특별시") if "서울특별시" in available_level1 else 0

    st.markdown(label_html("도/시를 골라주세요."), unsafe_allow_html=True)
    st.session_state.selected_level1 = st.selectbox(
        "", available_level1, index=default_level1_index, key="level1_selector"
    )

    available_level2 = (
        api.get_level2_list(st.session_state.selected_level1)
        if st.session_state.selected_level1 != "데이터 없음"
        else []
    ) or ["데이터 없음"]

    default_level2_index = (
        available_level2.index("강남구")
        if st.session_state.selected_level1 == "서울특별시" and "강남구" in available_level2
        else 0
    )

    st.markdown(label_html("군/구를 골라주세요."), unsafe_allow_html=True)
    st.session_state.selected_level2 = st.selectbox(
        "", available_level2, index=default_level2_index, key="level2_selector"
    )

with col_weather_info:
    st.subheader("현재 날씨")

    weather_data = api.get_weather(
        st.session_state.selected_level1, st.session_state.selected_level2
    )

    if debug_weather != "(API 사용)":
        weather_data = {
            "description": debug_weather,
            "temperature": 25,
            "humidity": 50,
            "precipitation": 1.2,
            "wsd": 2.5,
        }

    st.markdown(theme.weather_animation_html(weather_text), unsafe_allow_html=True)

    if weather_data and st.session_state.selected_level1 != "데이터 없음" and st.session_state.selected_level2 != "데이터 없음":
        temperature = weather_data.get("temperature", "N/A")
        st.markdown(
            f"""
            <div class='weather-content' style='background-color: white;'>
                <h3 style='text-align: center; margin-bottom: 10px; color: black;'>
                    {st.session_state.selected_level1} {st.session_state.selected_level2}
                </h3>
                <div class='weather-display'>
                    <video src="{weather_video}" autoplay loop muted style="width:100px; height:100px;"></video>
                    <span class='temperature'>{temperature if isinstance(temperature,str) else f"{temperature:.1f}"}°C</span>
                </div>
                <p class='weather-description'>{weather_text}</p>
                <p class='weather-detail'>습도: {weather_data.get('humidity', 'N/A')}%</p>
                <p class='weather-detail'>강수량: {weather_data.get('precipitation', 'N/A')} mm</p>
                <p class='weather-detail'>풍속: {weather_data.get('wsd', 'N/A')} m/s</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.info(f"날씨 정보를 가져올 수 없습니다. ({st.session_state.selected_level1} {st.session_state.selected_level2})")

with col_chart_rank:
    st.subheader("차트 순위")
    chart_items = api.get_chart_rank(limit=100)
    if chart_items:
        df_chart = pd.DataFrame(
            [
                {
                    "순위": item["rank"],
                    "가수": item["artist"],
                    "제목": item["title"],
                    "많이 나온 태그": " ".join(item.get("tags", [])[:3]) or "N/A",
                }
                for item in chart_items
            ]
        )
        st.dataframe(df_chart[["순위", "가수", "제목", "많이 나온 태그"]], hide_index=True)
    else:
        st.info("차트 순위를 가져올 수 없습니다.")

st.markdown("---")

# ---------------- Weather based recommendations -----
col_title, col_button = st.columns([10, 1])
with col_title:
    st.subheader("현재 날씨 기반 음악 추천")
with col_button:
    if st.button("New", key="refresh_recommendations"):
        st.session_state.refresh_key += 1
        st.cache_data.clear()
        st.rerun()

weather_recs = api.recommend_by_weather(
    st.session_state.selected_level1, st.session_state.selected_level2, randomize=True
)

if weather_recs:
    actual_music = [rec for rec in weather_recs if "artist" in rec]
    if actual_music:
        ui.render_grid(actual_music)
    else:
        st.info(weather_recs[0].get("message", "추천 결과가 없습니다."))
else:
    st.info("현재 날씨에 맞는 추천 음악이 없습니다.")

st.markdown("---")

# ---------------- Tag search ------------------------
col_search_title, col_new_button = st.columns([10, 1])
with col_search_title:
    st.subheader("태그로 음악 검색")
with col_new_button:
    if st.button("New", key="refresh_search"):
        st.session_state.search_refresh_key += 1
        st.cache_data.clear()
        st.rerun()

st.markdown(
    f"<div style='color: {header_text_color}; font-family: '"
    "'Comic Sans MS', 'Segoe UI Emoji', 'Arial', sans-serif;'>검색 키워드를 입력하세요 (예: kpop, summer, BTS, love 등)</div>",
    unsafe_allow_html=True,
)

st.session_state.search_query = st.text_input(
    "", value=st.session_state.search_query, key="music_search_input"
)

search_triggered = st.button("Search", key="search_button")

search_results = []
if search_triggered and st.session_state.search_query.strip():
    search_results = api.search_music(st.session_state.search_query.strip(), randomize=False)
elif st.session_state.search_refresh_key > 0 and st.session_state.search_query.strip():
    search_results = api.search_music(st.session_state.search_query.strip(), randomize=True)

if search_results:
    actual_search = [rec for rec in search_results if "artist" in rec]
    if actual_search:
        ui.render_grid(actual_search)
    else:
        st.info(search_results[0].get("message", "검색 결과가 없습니다."))
else:
    if search_triggered and not st.session_state.search_query.strip():
        st.warning("검색어를 입력해주세요.")

st.markdown("---")

# ---------------- Lyrics search ---------------------
col_lyrics_title, col_lyrics_new_button = st.columns([10, 1])
with col_lyrics_title:
    st.subheader("가사로 음악 검색")
with col_lyrics_new_button:
    if st.button("New", key="refresh_lyrics_search"):
        st.session_state.lyrics_search_refresh_key += 1
        st.cache_data.clear()
        st.rerun()

st.markdown(
    f"<div style='color: {header_text_color}; font-family: '"
    "'Comic Sans MS', 'Segoe UI Emoji', 'Arial', sans-serif;'>가사 키워드를 입력하세요 (예: love, breakup, summer 등)</div>",
    unsafe_allow_html=True,
)

st.session_state.lyrics_search_query = st.text_input(
    "", value=st.session_state.lyrics_search_query, key="lyrics_search_input"
)

lyrics_search_triggered = st.button("가사 검색", key="lyrics_search_button")

lyrics_results = []
if lyrics_search_triggered and st.session_state.lyrics_search_query.strip():
    lyrics_results = api.recommend_by_lyrics(st.session_state.lyrics_search_query.strip(), randomize=False)
elif st.session_state.lyrics_search_refresh_key > 0 and st.session_state.lyrics_search_query.strip():
    lyrics_results = api.recommend_by_lyrics(st.session_state.lyrics_search_query.strip(), randomize=True)

if lyrics_results:
    actual_lyrics = [rec for rec in lyrics_results if "artist" in rec]
    if actual_lyrics:
        ui.render_grid(actual_lyrics)
    else:
        st.info(lyrics_results[0].get("message", "검색 결과가 없습니다."))
else:
    if lyrics_search_triggered and not st.session_state.lyrics_search_query.strip():
        st.warning("가사 검색어를 입력해주세요.")
