import os
import json
import math
import pandas as pd
import streamlit as st
from lib import api, theme

FASTAPI_BACKEND_URL = api.FASTAPI_BASE_URL
ITEMS_PER_PAGE = 20
MAX_FETCH = 100
DATA_FILE = os.path.join(os.path.dirname(__file__), "chart_data.json")

st.set_page_config(layout="wide", page_title="음악 차트 순위")

# Keep background transparent
st.markdown("""
<style>
    [data-testid], [class*="css-"] { background: transparent !important; }
    .stApp, body { background: transparent !important; }
</style>
""", unsafe_allow_html=True)


def _fetch_and_cache_chart() -> pd.DataFrame:
    try:
        return pd.DataFrame(api.get_chart_rank(limit=MAX_FETCH))
    except Exception as e:  # pragma: no cover
        st.error(f"차트 데이터를 불러오는 중 오류: {e}")
        return pd.DataFrame()


def _load_or_init() -> pd.DataFrame:
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return pd.DataFrame(json.load(f))
    with st.spinner("차트 데이터를 로드 중입니다..."):
        df = _fetch_and_cache_chart()
        if not df.empty:
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(df.to_dict(orient="records"), f)
        return df


def main():
    weather_text = st.session_state.get("weather_text", "Clear")
    header_col = theme.header_color(weather_text)
    link_col = theme.link_color(weather_text)

    st.markdown(theme.weather_animation_html(weather_text), unsafe_allow_html=True)
    st.markdown(
        f"""
        <style>
            h1, h2, h3, p {{ color: {header_col} !important; }}
            .stTextInput label, .stSelectbox label {{ color: {header_col} !important; }}
            a {{ color: {link_col} !important; }}
            div[data-testid^="stButton"] > button {{
                font-family: 'Comic Sans MS', 'Segoe UI Emoji', 'Arial', sans-serif !important;
                border-color: black !important; background-color: white !important; color: black !important;
            }}
            div[data-testid^="stButton"] > button:hover {{ background-color: #e6e6e6 !important; }}
            div[data-testid^="stButton"] * {{ color: black !important; }}
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.title("음악 차트 순위")
    st.markdown("---")

    df = _load_or_init()
    if df.empty:
        st.info("표시할 차트 데이터가 없습니다.")
        return

    query = st.text_input("제목, 아티스트, 태그로 검색", "")
    if query:
        q = query.lower()
        df = df[
            df["title"].str.lower().str.contains(q)
            | df["artist"].str.lower().str.contains(q)
            | df["tags"].apply(lambda tags: any(q in t.lower() for t in tags))
        ]
        if df.empty:
            st.warning("검색 결과가 없습니다.")
            return
        
        if "last_query" not in st.session_state or st.session_state.last_query != query:
            st.session_state.current_page = 1
        st.session_state.last_query = query


    total_items = len(df)
    total_pages = max(1, math.ceil(total_items / ITEMS_PER_PAGE))

    if "current_page" not in st.session_state:
        st.session_state.current_page = 1

    def _set_page(new_page: int):
        st.session_state.current_page = max(1, min(total_pages, new_page))

    col1, col2, col3 = st.columns([1, 2, 1])
    with col1:
        if st.button("이전 페이지", disabled=st.session_state.current_page <= 1):
            _set_page(st.session_state.current_page - 1)
            st.rerun()
    with col2:
        st.markdown(f"<h3 style='text-align: center;'>페이지 {st.session_state.current_page} / {total_pages}</h3>", unsafe_allow_html=True)
    with col3:
        if st.button("다음 페이지", disabled=st.session_state.current_page >= total_pages):
            _set_page(st.session_state.current_page + 1)
            st.rerun()

    jump_col = st.columns([1, 8, 1])[2]
    with jump_col:
        go_to = st.selectbox(
            "페이지 이동",
            options=list(range(1, total_pages + 1)),
            index=st.session_state.current_page - 1,
            label_visibility="collapsed",
            key="page_select",
        )
        if go_to != st.session_state.current_page:
            _set_page(go_to)
            st.rerun()

    start = (st.session_state.current_page - 1) * ITEMS_PER_PAGE
    end = start + ITEMS_PER_PAGE
    display_df = df.iloc[start:end].reset_index(drop=True)

    st.markdown("---")

    headers = ["순위", "커버", "제목", "아티스트", "재생 수", "리스너 수", "YouTube 링크", "Spotify 링크"]
    widths = [0.5, 1, 2.5, 1.5, 1, 1, 1, 1]
    header_cols = st.columns(widths)
    for c, h in zip(header_cols, headers):
        c.markdown(f"<span style='color: {header_col};'>**{h}**</span>", unsafe_allow_html=True)

    for _, row in display_df.iterrows():
        cols = st.columns(widths)
        cols[0].write(f"**{row['rank']}**")
        if row["image_url"]:
            cols[1].image(row["image_url"], width=60)
        else:
            cols[1].markdown(
                """
                <div style="width: 60px;height: 60px;background-color: black;border-radius: 4px;display: inline-block;"></div>
                """,
                unsafe_allow_html=True,
            )

        if row["track_url"]:
            cols[2].markdown(
                f'<a href="{row["track_url"]}" target="_blank" style="color: {link_col};">{row["title"]}</a>',
                unsafe_allow_html=True,
            )
        else:
            cols[2].write(row["title"])

        if row["artist_url"]:
            cols[3].markdown(
                f'<a href="{row["artist_url"]}" target="_blank" style="color: {link_col};">{row["artist"]}</a>',
                unsafe_allow_html=True,
            )
        else:
            cols[3].write(row["artist"])

        cols[4].write(f"{row['play_cnt']:,}")
        cols[5].write(f"{row['listener_cnt']:,}")

        youtube_url = f"https://www.youtube.com/results?search_query={row['artist']}+{row['title']}"
        cols[6].link_button("YouTube", youtube_url, help="YouTube에서 듣기")

        spotify_url = f"https://open.spotify.com/search/{row['artist']}%20{row['title']}"
        cols[7].link_button("Spotify", spotify_url, help="Spotify에서 듣기")


if __name__ == "__main__":
    main()
