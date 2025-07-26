import pandas as pd
import streamlit as st
import urllib.parse
from lib import theme
from lib.db import get_redshift_connection_internal  # Redshift 직접 연결용

# Keep background transparent
st.markdown("""
<style>
    [data-testid], [class*="css-"] { background: transparent !important; }
    .stApp, body { background: transparent !important; }
</style>
""", unsafe_allow_html=True)

st.set_page_config(layout="wide", page_title="가사 차트")

ITEMS_PER_PAGE = 20  # chart_rank.py 참고

# --- 숫자 포맷팅 안전 함수 ---
def safe_format_int(value):
    try:
        return f"{int(float(value)):,}"
    except (ValueError, TypeError):
        return ""

# ✅ 지역 리스트 Redshift에서 직접 가져오기
def get_available_regions():
    try:
        conn = get_redshift_connection_internal()
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT region FROM raw_data.weather_music ORDER BY region;")
        return [r[0] for r in cursor.fetchall()]
    except Exception as e:
        st.error(f"[ERROR] 시/도 목록을 불러오지 못했습니다: {e}")
        return []
    finally:
        if conn:
            conn.close()

# ✅ 차트 데이터 Redshift에서 직접 가져오기
def get_lyrics_chart_simple(level1, limit=500):
    try:
        conn = get_redshift_connection_internal()
        cursor = conn.cursor()
        query = """
            SELECT region, weather, track_name, album_title, artist_name, album_image_url, album_url, track_url,
                listeners, playcount, headline, run_time
            FROM raw_data.weather_music
            WHERE region = %s
            ORDER BY run_time DESC
            LIMIT %s;
        """
        cursor.execute(query, (level1, limit))
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    except Exception as e:
        st.error(f"[ERROR] 차트 데이터를 불러올 수 없습니다: {e}")
        return []
    finally:
        if conn:
            conn.close()

# --- 메인 로직 ---
def main():
    st.title("가사 차트")
    st.markdown("---")

    if "lyrics_current_page" not in st.session_state:
        st.session_state.lyrics_current_page = 1

    available_level1 = get_available_regions()
    if not available_level1:
        available_level1 = ["데이터 없음"]
        st.warning("시/도 목록을 불러올 수 없습니다.")

    default_idx = available_level1.index("서울특별시") if "서울특별시" in available_level1 else 0
    selected_level1 = st.selectbox("시/도 선택", available_level1, index=default_idx, key="lyrics_level1_selector")

    if selected_level1 and selected_level1 != "데이터 없음":
        chart_data = get_lyrics_chart_simple(selected_level1)

        if chart_data:
            df = pd.DataFrame(chart_data)
            df.columns = [col.lower() for col in df.columns]

            if "run_time" in df.columns:
                df["run_time"] = pd.to_datetime(df["run_time"], errors="coerce")
                df = df.sort_values("run_time", ascending=False)

            if all(c in df.columns for c in ["track_name", "artist_name"]):
                df = df.drop_duplicates(subset=["track_name", "artist_name"], keep="first")

            total_items = len(df)
            total_pages = max(1, (total_items + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)

            def set_page(new_page: int):
                st.session_state.lyrics_current_page = max(1, min(total_pages, new_page))

            col1, col2, col3 = st.columns([1, 2, 1])
            with col1:
                if st.button("이전 페이지", disabled=st.session_state.lyrics_current_page <= 1, key="lyrics_prev_page"):
                    set_page(st.session_state.lyrics_current_page - 1)
                    st.rerun()
            with col2:
                st.markdown(f"<h3 style='text-align: center;'>페이지 {st.session_state.lyrics_current_page} / {total_pages}</h3>", unsafe_allow_html=True)
            with col3:
                if st.button("다음 페이지", disabled=st.session_state.lyrics_current_page >= total_pages, key="lyrics_next_page"):
                    set_page(st.session_state.lyrics_current_page + 1)
                    st.rerun()

            jump_col = st.columns([1, 8, 1])[2]
            with jump_col:
                go_to = st.selectbox(
                    "페이지 이동",
                    options=list(range(1, total_pages + 1)),
                    index=st.session_state.lyrics_current_page - 1,
                    label_visibility="collapsed",
                    key="lyrics_page_select",
                )
                if go_to != st.session_state.lyrics_current_page:
                    set_page(go_to)
                    st.rerun()

            start = (st.session_state.lyrics_current_page - 1) * ITEMS_PER_PAGE
            end = start + ITEMS_PER_PAGE
            display_df = df.iloc[start:end].reset_index(drop=True)

            title_col = next((c for c in ["track_name", "title", "name", "song_name"] if c in df.columns), None)
            weather_text = display_df.iloc[0].get("weather", "Clear") if not display_df.empty else "Clear"
            header_col = theme.header_color(weather_text)
            link_col = theme.link_color(weather_text)

            st.markdown(theme.weather_animation_html(weather_text), unsafe_allow_html=True)
            theme.inject_global_css(header_col)

            headline = display_df.iloc[0].get("headline", "헤드라인이 없습니다.") if not display_df.empty else "헤드라인이 없습니다."
            st.markdown(f"<h3 style='color: {header_col};'>헤드라인: {headline}</h3>", unsafe_allow_html=True)
            st.markdown(f"<p style='color: {header_col};'>현재 날씨: {weather_text}</p>", unsafe_allow_html=True)
            st.markdown("---")

            display_rows = []
            for idx, item in enumerate(display_df.to_dict(orient="records")):
                title = item.get(title_col, "제목 없음") if title_col else "N/A"
                artist = item.get("artist_name", "N/A")
                row = {
                    "순위": f"**{start + idx + 1}**",
                    "커버": item.get("album_image_url", ""),
                    "제목": title,
                    "아티스트": artist,
                    "YouTube 링크": f"https://www.youtube.com/results?search_query={urllib.parse.quote(artist)}%20{urllib.parse.quote(title)}",
                    "Spotify 링크": f"https://open.spotify.com/search/{urllib.parse.quote(artist)}%20{urllib.parse.quote(title)}",
                }

                if item.get("track_url"):
                    row["label"] = f'<a href="{item["track_url"]}" target="_blank" style="color: {link_col}">{title}</a>'
                    row["아티스트"] = f'<a href="{item["track_url"]}" target="_blank" style="color: {link_col}">{artist}</a>'

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
                        cols[i].link_button(h.replace(" ", ""), row[h])
                    else:
                        cols[i].markdown(row[h], unsafe_allow_html=True)
        else:
            st.warning(f"'{selected_level1}'에 대한 차트 데이터를 불러올 수 없습니다.")
    else:
        st.warning("시/도 목록을 선택해주세요.")

if __name__ == "__main__":
    main()
