from __future__ import annotations
import streamlit as st
from typing import Dict, List

def music_card(rec: Dict) -> None:
    """Render a single music recommendation card."""
    img_html = (
        f"<img src='{rec['image_url']}' class='music-image'>"
        if rec.get("image_url") and rec["image_url"].strip()
        else "<div class='no-image-placeholder'>No Image</div>"
    )

    artist_link = (
        f"<a href='{rec['artist_url']}' target='_blank'>아티스트 페이지</a>"
        if rec.get("artist_url") and rec["artist_url"].strip()
        else "<span class='link-placeholder'>아티스트 페이지 없음</span>"
    )
    track_link = (
        f"<a href='{rec['track_url']}' target='_blank'>트랙 페이지</a>"
        if rec.get("track_url") and rec["track_url"].strip()
        else "<span class='link-placeholder'>트랙 페이지 없음</span>"
    )
    tags = " ".join(rec.get("tags", [])) or "No Tags"

    st.markdown(
        f"""
        <div class='music-card'>
            <div class='image-wrapper'>
                {img_html}
            </div>
            <div class='music-info-box'>
                <p class='artist-name'>{rec.get('artist','')}</p>
                <p class='track-title'>{rec.get('title','')}</p>
            </div>
            <div class='music-link-box'>{artist_link}</div>
            <div class='music-link-box'>{track_link}</div>
            <div class='music-tags-box'><p class='tags-text'>{tags}</p></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

def render_grid(records: List[Dict], cols_per_row: int = 5, rows: int = 2):
    """Render recommendation/search results in a fixed grid."""
    max_items = cols_per_row * rows
    records = records[:max_items]
    for row in range(rows):
        start = row * cols_per_row
        end = start + cols_per_row
        cols = st.columns(cols_per_row)
        for i, rec in enumerate(records[start:end]):
            with cols[i]:
                music_card(rec)