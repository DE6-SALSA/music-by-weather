import streamlit as st
import requests
import pandas as pd

FASTAPI_BACKEND_URL = "http://localhost:8000"
ITEMS_PER_PAGE = 20

st.set_page_config(layout="wide", page_title="음악 차트 순위")

def show_chart_rank_page():
    st.title("음악 차트 순위")
    st.markdown("---")

    # 데이터 로드
    @st.cache_data(ttl=300)
    def get_chart_data():
        try:
            response = requests.get(f"{FASTAPI_BACKEND_URL}/chart_rank")
            response.raise_for_status()
            return pd.DataFrame(response.json())
        except requests.exceptions.ConnectionError:
            st.error("백엔드 서버에 연결할 수 없습니다. FastAPI 서버가 실행 중인지 확인해주세요.")
            return pd.DataFrame()
        except requests.exceptions.RequestException as e:
            st.error(f"데이터를 가져오는 중 오류가 발생했습니다: {e}")
            return pd.DataFrame()

    df = get_chart_data()

    if df.empty:
        st.info("표시할 차트 데이터가 없습니다.")
        return

    # 검색
    search_query = st.text_input("제목, 아티스트, 태그로 검색", "")
    if search_query:
        search_query_lower = search_query.lower()
        df = df[
            df['title'].str.lower().str.contains(search_query_lower) |
            df['artist'].str.lower().str.contains(search_query_lower) |
            df['tags'].apply(lambda tags: any(search_query_lower in t.lower() for t in tags))
        ]

    if df.empty:
        st.warning("검색 결과가 없습니다.")
        return

    # 페이지네이션
    total_items = len(df)
    total_pages = (total_items + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
    if 'current_page' not in st.session_state:
        st.session_state.current_page = 1

    col1, col2, col3 = st.columns([1, 2, 1])
    with col1:
        if st.button("이전 페이지", disabled=(st.session_state.current_page == 1)):
            st.session_state.current_page -= 1
            st.rerun()
    with col2:
        st.markdown(f"<h3 style='text-align: center;'>페이지 {st.session_state.current_page} / {total_pages}</h3>", unsafe_allow_html=True)
    with col3:
        if st.button("다음 페이지", disabled=(st.session_state.current_page == total_pages)):
            st.session_state.current_page += 1
            st.rerun()

    start_idx = (st.session_state.current_page - 1) * ITEMS_PER_PAGE
    end_idx = start_idx + ITEMS_PER_PAGE
    display_df = df.iloc[start_idx:end_idx].reset_index(drop=True)

    st.markdown("---")

    # 테이블 헤더
    header_cols = st.columns([0.5, 1, 3, 2, 1.5, 1.5, 0.5])
    header_cols[0].write("**순위**")
    header_cols[1].write("**커버**")
    header_cols[2].write("**제목**")
    header_cols[3].write("**아티스트**")
    header_cols[4].write("**재생 수**")
    header_cols[5].write("**리스너 수**")
    header_cols[6].write("**상세**")

    # 데이터 행
    for _, row in display_df.iterrows():
        actual_rank = row['rank']
        cols = st.columns([0.5, 1, 3, 2, 1.5, 1.5, 0.5])

        # 순위
        cols[0].write(f"**{actual_rank}**")

        # 앨범 커버
        if row['image_url']:
            cols[1].image(row['image_url'], width=60)
        else:
            cols[1].markdown(
                """
                <div style="
                    width: 60px;
                    height: 60px;
                    background-color: black;
                    border-radius: 4px;
                    display: inline-block;
                "></div>
                """,
                unsafe_allow_html=True
            )


        # 제목
        if row['track_url']:
            cols[2].markdown(f"[{row['title']}]({row['track_url']})")
        else:
            cols[2].write(row['title'])

        # 아티스트
        if row['artist_url']:
            cols[3].markdown(f"[{row['artist']}]({row['artist_url']})")
        else:
            cols[3].write(row['artist'])

        # 재생 수
        cols[4].write(f"{row['play_cnt']:,}")

        # 리스너 수
        cols[5].write(f"{row['listener_cnt']:,}")

        # 상세 팝업
        with cols[6]:
            with st.popover("상세 보기"):
                st.subheader(row['title'])
                st.write(f"**아티스트:** {row['artist']}")
                st.write(f"**재생 수:** {row['play_cnt']:,}")
                st.write(f"**리스너 수:** {row['listener_cnt']:,}")
                if row['image_url']:
                    st.image(row['image_url'], caption=f"{row['title']} 커버", width=200)
                st.markdown("---")
                st.write("외부 링크:")
                if row['track_url']:
                    st.link_button("Last.fm 트랙 페이지", row['track_url'])
                if row['artist_url']:
                    st.link_button("Last.fm 아티스트 페이지", row['artist_url'])
                st.link_button("YouTube에서 듣기", f"https://www.youtube.com/results?search_query={row['artist']}+{row['title']}")
                st.link_button("Spotify에서 듣기", f"https://open.spotify.com/search/{row['artist']}%20{row['title']}")

if __name__ == "__main__":
    show_chart_rank_page()
