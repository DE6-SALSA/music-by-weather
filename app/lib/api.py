
# app/lib/api.py
"""
FastAPI 백엔드 호출 래퍼 모듈.

- requests.Session 재사용으로 효율↑
- 모든 GET은 _get() 한 곳에서 처리
- Streamlit cache_data 로 과도한 호출 방지
- urllib.parse.quote 제거 → requests 가 알아서 인코딩
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
import requests
import streamlit as st
from airflow.models import Variable
from constants import FASTAPI_BASE_URL

# ---------------------------------------------------------------------
# 기본 설정
# ---------------------------------------------------------------------
FASTAPI_BASE_URL: str = Variable.get("fastapi_base_url", default_var="http://10.0.45.211:8000").rstrip("/")

_SESSION = requests.Session()
_TIMEOUT = 100  # seconds

def _get(path: str, **params) -> requests.Response:
    url = f"{FASTAPI_BASE_URL}{path}"
    print(f"[DEBUG] Requesting URL: {url} with params: {params}")  # 디버깅 추가
    resp = _SESSION.get(url, params=params or None, timeout=_TIMEOUT)
    resp.raise_for_status()
    return resp

# ---------------------------------------------------------------------
# 실제 API 래퍼들 (캐시)
# ---------------------------------------------------------------------

@st.cache_data(ttl=3600)
def get_level1_list() -> List[str]:
    try:
        resp = _get("/locations/level1")
        print(f"[DEBUG] Level1 response: {resp.json()}")  # 디버깅 추가
        return resp.json()
    except requests.exceptions.RequestException as e:
        st.error(f"시/도 목록을 가져오는 중 오류: {e}")
        return []

@st.cache_data(ttl=3600)
def get_level2_list(level1_name: str) -> List[str]:
    if not level1_name:
        return []
    try:
        resp = _get("/locations/level2", level1_name=level1_name)
        print(f"[DEBUG] Level2 response for {level1_name}: {resp.json()}")  # 디버깅 추가
        return resp.json()
    except requests.exceptions.RequestException as e:
        st.error(f"시/군/구 목록을 가져오는 중 오류: {e}")
        return []

@st.cache_data(ttl=3600)
def get_weather(level1: str, level2: str) -> Dict[str, Any]:
    if not (level1 and level2):
        return {}
    try:
        return _get("/weather/current", level1=level1, level2=level2).json()
    except requests.exceptions.RequestException as e:
        st.error(f"날씨 정보를 가져오는 중 오류: {e}")
        return {}

@st.cache_data(ttl=300)
def get_chart_rank(limit: int = 100) -> List[Dict[str, Any]]:
    try:
        return _get("/chart_rank", limit=limit).json()
    except requests.exceptions.RequestException as e:
        st.error(f"차트 순위 호출 오류: {e}")
        return []

@st.cache_data(ttl=300)
def recommend_by_weather(location: str, sub_location: str, limit: int = 20, randomize: bool = False) -> List[Dict[str, Any]]:
    if not location:
        return []
    try:
        params: Dict[str, Any] = {"location": location, "limit": limit}
        if sub_location:
            params["sub_location"] = sub_location
        if randomize:
            params["randomize"] = True
        return _get("/recommend/weather", **params).json()
    except requests.exceptions.RequestException as e:
        st.error(f"날씨 기반 추천 오류: {e}")
        return []

@st.cache_data(ttl=300)
def search_music(query: str, limit: int = 20, randomize: bool = False) -> List[Dict[str, Any]]:
    if not query:
        return []
    try:
        params: Dict[str, Any] = {"query": query, "limit": limit}
        if randomize:
            params["randomize"] = True
        return _get("/search/music", **params).json()
    except requests.exceptions.RequestException as e:
        st.error(f"음악 검색 오류: {e}")
        return []

@st.cache_data(ttl=300)
def recommend_by_lyrics(query: str, limit: int = 20, randomize: bool = False) -> List[Dict[str, Any]]:
    if not query:
        return []
    try:
        params: Dict[str, Any] = {"query": query, "limit": limit}
        if randomize:
            params["randomize"] = True
        return _get("/recommend/lyrics", **params).json()
    except requests.exceptions.RequestException as e:
        st.error(f"가사 기반 추천 오류: {e}")
        return []
