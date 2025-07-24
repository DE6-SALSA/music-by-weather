from typing import List, Dict, Optional, Union
from fastapi import APIRouter, HTTPException, Query

from services import (
    get_current_weather_from_redshift_internal,
    recommend_music_by_weather_service,
    search_music_service,
    get_chart_rank_service,
    get_level1_list_service,
    get_level2_list_service,
)

router = APIRouter()

@router.get("/weather/current", response_model=Dict[str, Union[str, float, int]])
async def get_current_weather(level1: str = Query(..., description="시/도 이름"),
                              level2: str = Query(..., description="시/군/구 이름")):
    weather_info = get_current_weather_from_redshift_internal(level1, level2)
    if not weather_info:
        raise HTTPException(status_code=404, detail=f"{level1} {level2}에 대한 날씨 정보를 찾을 수 없습니다.")
    return weather_info

@router.get("/locations/level1", response_model=List[str])
async def get_level1_list():
    return get_level1_list_service()

@router.get("/locations/level2", response_model=List[str])
async def get_level2_list(level1_name: str = Query(..., description="조회할 level1 (시/도) 이름")):
    return get_level2_list_service(level1_name)

@router.get("/recommend/weather", response_model=List[Dict])
async def recommend_music_by_weather(location: str = "서울특별시",
                                    sub_location: Optional[str] = None,
                                    randomize: bool = Query(False, description="무작위 추천 여부")):
    return await recommend_music_by_weather_service(location, sub_location, randomize)

@router.get("/search/music", response_model=List[Dict], tags=["Music Search"])
async def search_music(query: str = Query(..., min_length=2, description="검색할 곡명, 아티스트, 앨범 또는 태그"),
                       limit: int = Query(20, description="반환할 결과의 최대 개수"),
                       randomize: bool = Query(False, description="무작위 추천 여부")):
    return await search_music_service(query, limit, randomize)

@router.get("/chart_rank", response_model=List[Dict])
async def get_chart_rank(limit: int = 100):
    return await get_chart_rank_service(limit)
