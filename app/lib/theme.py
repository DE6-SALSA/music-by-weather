from __future__ import annotations
import streamlit as st
from pathlib import Path
from typing import Callable, Dict
from assets import animations

# Weather -> html function map
ANIMATIONS: Dict[str, Callable[[], str]] = {
    "Clear": animations.clear_html,
    "Rainy": animations.rainy_html,
    "Snowy": animations.snowy_html,
    "Cloudy": animations.cloudy_html,
    "Windy": animations.windy_html,
    "Stormy": animations.stormy_html,
    "Hot": animations.hot_html,
    "Cold": animations.cold_html,
}

# Weather -> video url map
WEATHER_VIDEO = {
    "Clear": "https://cdn-icons-mp4.flaticon.com/512/17102/17102813.mp4",
    "Rainy": "https://cdn-icons-mp4.flaticon.com/512/17102/17102963.mp4",
    "Snowy": "https://cdn-icons-mp4.flaticon.com/512/17484/17484878.mp4",
    "Windy": "https://cdn-icons-mp4.flaticon.com/512/17102/17102829.mp4",
    "Cloudy": "https://cdn-icons-mp4.flaticon.com/512/17102/17102874.mp4",
    "Stormy": "https://cdn-icons-mp4.flaticon.com/512/17102/17102956.mp4",
    "Hot":   "https://cdn-icons-mp4.flaticon.com/512/17103/17103056.mp4",
    "Cold":  "https://cdn-icons-mp4.flaticon.com/512/17103/17103071.mp4",
}

# Dynamic colors for headers & links
COLD_COLORS = {"Rainy", "Snowy", "Stormy", "Cold"}

LINK_COLOR_MAP = {
    "Clear": "#0000FF",
    "Cloudy": "#0000FF",
    "Rainy": "#FFFFFF",
    "Snowy": "#FFFE05",
    "Cold": "#F58186",
    "Stormy": "#FFFF00",
    "Windy": "#560279",
    "Hot": "#4D56EE",
}

def header_color(weather: str) -> str:
    return "white" if weather in COLD_COLORS else "black"

def link_color(weather: str) -> str:
    return LINK_COLOR_MAP.get(weather, "#000000")

def inject_global_css(header_text_color: str):
    """Inject global css overrides that depend on header color."""
    st.markdown(f"""
    <style>
        [data-testid], [class*="css-"] {{ background: transparent !important; }}
        .stApp, body {{ background: transparent !important; }}
        h2, h3, h4, h5, h6 {{
            font-family: 'Comic Sans MS', 'Segoe UI Emoji', 'Arial', sans-serif !important;
            color: {header_text_color} !important;
        }}
        div[data-testid="stWidgetLabel"] > label {{
            font-family: 'Comic Sans MS', 'Segoe UI Emoji', 'Arial', sans-serif !important;
            color: {header_text_color} !important;
        }}
        div[data-testid="stSidebarNav"] a,
        div[data-testid="stSidebarNav"] li > div {{ color: white !important; }}
        div[data-testid="stSidebarNav"] li > div[data-selected="true"] {{ color: white !important; }}
        .stSelectbox > div > div > div > div svg {{ fill: black; }}
        .stButton > button {{
            font-family: 'Comic Sans MS', 'Segoe UI Emoji', 'Arial', sans-serif !important;
            border-color: black !important;
            background-color: white !important;
            color: black !important;
        }}
        .stButton > button:hover {{ background-color: #e6e6e6 !important; }}
        a[data-testid*="stLinkButton"] {{
            font-family: 'Comic Sans MS', 'Segoe UI Emoji', 'Arial', sans-serif !important;
            background-color: white !important;
            border-color: black !important;
            padding: 0.25rem 0.75rem;
            border-radius: 0.25rem;
            text-decoration: none;
            display: inline-flex; align-items: center; justify-content: center;
            font-weight: 400; line-height: 1.6; text-align: center; white-space: nowrap; user-select: none;
            transition: color .15s ease-in-out,background-color .15s ease-in-out,border-color .15s ease-in-out,box-shadow .15s ease-in-out;
        }}
        a[data-testid*="stLinkButton"]:hover {{ background-color: #f0f2f6 !important; }}
        div.weather-content p, div.weather-content * {{ color: #000000 !important; }}
        .weather-display video {{ background: transparent !important; }}
        .music-card p, .music-info-box .artist-name, .music-info-box .track-title, .music-tags-box .tags-text {{ color: black !important; }}
    </style>
    """, unsafe_allow_html=True)


def load_css(path: str | Path):
    with open(path, "r", encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


def weather_animation_html(weather: str) -> str:
    return ANIMATIONS.get(weather, animations.clear_html)()
