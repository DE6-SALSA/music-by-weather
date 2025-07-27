import os
import math
import requests
import pandas as pd
import urllib.parse
import streamlit as st
from lib import theme

API_BASE_URL = api.FASTAPI_BASE_URL

st.markdown("""
<style>
    [data-testid], [class*="css-"] { background: transparent !important; }
    .stApp, body { background: transparent !important; }
</style>
""", unsafe_allow_html=True)

st.set_page_config(layout="wide", page_title="가사 차트")

# --- API 호출 함수 ---
def get_level1_list():
    try:
        res = requests.get("http://127.0.0.1:8000/locations/level1")
        res.raise_for_status()
        return res.json()
    except Exception as e:
        st.error(f"시/도 API 오류: {e}")
        return []

def get_lyrics_chart(level1: str, limit: int = 100):
    try:
        url = f"http://127.0.0.1:8000/chart/lyrics_simple?level1={urllib.parse.quote(level1)}&limit={limit}"
        res = requests.get(url)
        res.raise_for_status()
        return res.json()
    except Exception as e:
        st.error(f"가사 차트 API 오류: {e}")
        return []

# --- 숫자 포맷팅 안전 함수 ---
def safe_format_int(value):
    try:
        return f"{int(float(value)):,}"
    except (ValueError, TypeError):
        return ""

# --- 메인 로직 ---
def main():
    st.title("가사 차트")
    st.markdown("---")

    available_level1 = get_level1_list()
    if not available_level1:
        available_level1 = ["데이터 없음"]

    default_idx = available_level1.index("서울특별시") if "서울특별시" in available_level1 else 0
    selected_level1 = st.selectbox("시/도 선택", available_level1, index=default_idx, key="lyrics_level1_selector")

    if selected_level1 and selected_level1 != "데이터 없음":
        chart_data = get_lyrics_chart(selected_level1)

        if chart_data:
            df = pd.DataFrame(chart_data)
            df.columns = [col.lower() for col in df.columns]

            if "run_time" in df.columns:
                df["run_time"] = pd.to_datetime(df["run_time"], errors="coerce")
                df = df.sort_values("run_time", ascending=False)

            if all(c in df.columns for c in ["track_name", "artist_name"]):
                df = df.drop_duplicates(subset=["track_name", "artist_name"], keep="first")

            title_col = next((c for c in ["track_name", "title", "name", "song_name"] if c in df.columns), None)

            # ✅ 날씨 값 기반으로 테마/배경 적용
            weather_text = df.iloc[0].get("weather", "Clear")
            header_col = theme.header_color(weather_text)
            link_col = theme.link_color(weather_text)

            st.markdown(theme.weather_animation_html(weather_text), unsafe_allow_html=True)
            theme.inject_global_css(header_col)

            headline = df.iloc[0].get("headline", "헤드라인이 없습니다.")
            st.markdown(f"<h3 style='color: {header_col};'>헤드라인: {headline}</h3>", unsafe_allow_html=True)
            st.markdown(f"<p style='color: {header_col};'>현재 날씨: {weather_text}</p>", unsafe_allow_html=True)
            st.markdown("---")

            display_rows = []
            for idx, item in enumerate(df.to_dict(orient="records")):
                title = item.get(title_col, "제목 없음") if title_col else "제목 없음"
                artist = item.get("artist_name", "N/A")
                row = {
                    "순위": f"**{idx + 1}**",
                    "커버": item.get("album_image_url", ""),
                    "제목": title,
                    "아티스트": artist,
                    "YouTube 링크": f"https://www.youtube.com/results?search_query={urllib.parse.quote(artist)}+{urllib.parse.quote(title)}",
                    "Spotify 링크": f"https://open.spotify.com/search/{urllib.parse.quote(artist)}%20{urllib.parse.quote(title)}",
                }

                if item.get("track_url"):
                    row["제목"] = f'<a href="{item["track_url"]}" target="_blank" style="color: {link_col};">{title}</a>'
                    row["아티스트"] = f'<a href="{item["track_url"]}" target="_blank" style="color: {link_col};">{artist}</a>'

                if item.get("listeners") is not None and pd.notna(item["listeners"]):
                    row["리스너 수"] = safe_format_int(item["listeners"])
                if item.get("playcount") is not None and pd.notna(item["playcount"]):
                    row["재생 수"] = safe_format_int(item["playcount"])

                display_rows.append(row)

            display_df = pd.DataFrame(display_rows)

            base_headers = ["순위", "커버", "제목", "아티스트"]
            optional_headers = []
            if "리스너 수" in display_df.columns:
                optional_headers.append("리스너 수")
            if "재생 수" in display_df.columns:
                optional_headers.append("재생 수")
            link_headers = ["YouTube 링크", "Spotify 링크"]

            headers = base_headers + optional_headers + link_headers
            widths = [0.5, 1, 2, 1.5] + [1] * len(optional_headers) + [1, 1]

            header_cols = st.columns(widths)
            for col, head in zip(header_cols, headers):
                col.markdown(f"<span style='color: {header_col}; font-weight:bold;'>{head}</span>", unsafe_allow_html=True)

            for _, row in display_df.iterrows():
                cols = st.columns(widths)
                for i, h in enumerate(headers):
                    if h == "커버":
                        if row[h]:
                            cols[i].image(row[h], width=60)
                        else:
                            cols[i].markdown(
                                "<div style='width: 60px; height: 60px; background-color: black; border-radius: 4px;'></div>",
                                unsafe_allow_html=True,
                            )
                    elif h in link_headers:
                        cols[i].link_button(h.replace(" 링크", ""), row[h])
                    else:
                        cols[i].markdown(row[h], unsafe_allow_html=True)
        else:
            st.warning(f"'{selected_level1}'에 대한 차트 데이터를 불러오지 못했습니다.")
    else:
        st.warning("시/도 목록을 선택해주세요.")

if __name__ == "__main__":
    main()
