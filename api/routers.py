import asyncio
from typing import List, Dict, Optional, Union
from fastapi import APIRouter, HTTPException, Query
from db import get_redshift_connection_internal
from services import get_current_weather_from_redshift_internal, get_music_data_from_redshift_internal

router = APIRouter()

@router.get("/weather/current", response_model=Dict[str, Union[str, float, int]]) 
async def get_current_weather(level1: str = Query(..., description="시/도 이름"), level2: str = Query(..., description="시/군/구 이름")):
    weather_info = get_current_weather_from_redshift_internal(level1, level2)
    if not weather_info:
        raise HTTPException(status_code=404, detail=f"{level1} {level2}에 대한 날씨 정보를 찾을 수 없습니다.")
    return weather_info

@router.get("/recommend/weather", response_model=List[Dict])
async def recommend_music_by_weather(location: str = "서울특별시", sub_location: Optional[str] = None, randomize: bool = Query(False, description="무작위 추천 여부")): 
    weather_info = get_current_weather_from_redshift_internal(location, sub_location if sub_location else "강남구")
    current_condition = weather_info.get("description") 

    if not current_condition: 
        raise HTTPException(status_code=500, detail=f"{location} {sub_location if sub_location else '강남구'}의 날씨 정보를 Redshift에서 가져올 수 없습니다.")

    print(f"날씨 정보: {location}, 조건: {current_condition}") 

    recommended_music = await get_music_data_from_redshift_internal(weather_condition=current_condition, randomize=randomize)

    if not recommended_music:
        fallback_music = await get_music_data_from_redshift_internal(limit=5) 
        if not fallback_music:
            return [{"message": f"{location}의 {current_condition} 날씨에 맞는 추천 음악을 찾을 수 없습니다. 현재 데이터베이스에 추천할 음악이 없습니다."}]
        return [{"message": f"{location}의 {current_condition} 날씨에 맞는 추천 음악을 찾을 수 없습니다. 다른 인기 음악을 추천합니다."},
                *fallback_music]
    
    return recommended_music

@router.get("/search/music", response_model=List[Dict], tags=["Music Search"]) 
async def search_music(
    query: str = Query(..., min_length=2, description="검색할 곡명, 아티스트, 앨범 또는 태그"),
    limit: int = Query(20, description="반환할 결과의 최대 개수"),
    randomize: bool = Query(False, description="무작위 추천 여부")
):
    if not query:
        raise HTTPException(status_code=400, detail="검색어를 입력해주세요.")
    
    music_results = await get_music_data_from_redshift_internal(search_query=query, limit=limit, randomize=randomize) 
    
    if not music_results:
        raise HTTPException(status_code=404, detail=f"'{query}'에 대한 검색 결과를 찾을 수 없습니다.")
    
    return music_results

@router.get("/chart_rank", response_model=List[Dict])
async def get_chart_rank(limit: int = 100):
    music_rank_data = []
    conn = None
    cur = None
    try:
        conn = get_redshift_connection_internal()
        cur = conn.cursor()

        select_clause = "artist, title, play_cnt, listener_cnt, tag1, tag2, tag3, tag4, tag5"

        query = f"""
            SELECT {select_clause}
            FROM analytics_data.top_tag5
            ORDER BY play_cnt DESC, listener_cnt DESC
            LIMIT %s;
        """
        print(f"[DEBUG] Executing chart rank query: {query.strip()} with limit={limit}")
        cur.execute(query, (limit,))
        music_records = cur.fetchall()

        print(f"[DEBUG] Number of chart rank records fetched: {len(music_records)}")
        if music_records:
            print(f"[DEBUG] First chart rank record: {music_records[0]}")

        columns = [desc[0] for desc in cur.description]
        
        lastfm_tasks = []
        
        from .services import get_lastfm_track_info # Import here to avoid circular dependency if router imports service and service imports router

        for i, record in enumerate(music_records):
            music_dict = dict(zip(columns, record))
            combined_tags = [
                music_dict[f'tag{j}'] for j in range(1, 6)
                if music_dict.get(f'tag{j}') and music_dict[f'tag{j}'].strip() != ''
            ]
            music_dict['tags'] = combined_tags
            for j in range(1, 6):
                if f'tag{j}' in music_dict:
                    del music_dict[f'tag{j}']

            music_dict['rank'] = i + 1 
            
            lastfm_tasks.append(get_lastfm_track_info(music_dict['artist'], music_dict['title']))
            music_rank_data.append(music_dict)

        lastfm_results = await asyncio.gather(*lastfm_tasks, return_exceptions=True)

        for i, lastfm_info in enumerate(lastfm_results):
            if isinstance(lastfm_info, Exception):
                print(f"[ERROR] Last.fm API call failed for rank {i+1}: {music_rank_data[i]['artist']} - {music_rank_data[i]['title']}, Error: {lastfm_info}")
                music_rank_data[i].update({"image_url": "", "artist_url": "", "track_url": ""})
            else:
                music_rank_data[i].update(lastfm_info)
                print(f"[DEBUG] Integrated Last.fm data for rank {i+1}: {music_rank_data[i]['artist']} - {music_rank_data[i]['title']}, Image: {music_rank_data[i]['image_url']}")

    except HTTPException as e:
        print(f"[DEBUG] HTTPException in get_chart_rank: {e}")
        raise e
    except Exception as e:
        print(f"Redshift에서 차트 순위 데이터를 가져오는 중 오류 발생: {e}")
        raise HTTPException(status_code=500, detail=f"차트 순위 데이터를 가져오는 중 오류가 발생했습니다: {e}")
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()
    
    if not music_rank_data:
        print(f"[DEBUG] No chart rank data found")
        raise HTTPException(status_code=404, detail="차트 순위 데이터를 찾을 수 없습니다.")

    return music_rank_data

@router.get("/chart/lyrics_simple", response_model=List[Dict])
async def get_lyrics_chart_simple(level1: str = Query(..., description="시/도 이름"), limit: int = Query(100, description="반환할 결과의 최대 개수")):
    conn = None
    cur = None
    music_data = []
    try:
        conn = get_redshift_connection_internal()
        cur = conn.cursor()

        query = """
            SELECT region, weather, track_name, album_title, artist_name, album_image_url, album_url, track_url,
                listeners, playcount, headline, run_time
            FROM raw_data.weather_music
            WHERE region = %s
            ORDER BY run_time DESC
            LIMIT %s;
        """
        print(f"[DEBUG] Executing simple lyrics chart query for level1={level1}: {query}")
        cur.execute(query, (level1, limit))
        music_records = cur.fetchall()

        print(f"[DEBUG] Number of simple lyrics chart records fetched: {len(music_records)}")
        if music_records:
            print(f"[DEBUG] First simple lyrics chart record: {music_records[0]}")

        columns = [desc[0] for desc in cur.description]
        for i, record in enumerate(music_records):
            music_dict = dict(zip(columns, record))
            music_dict['rank'] = i + 1
            music_data.append(music_dict)

    except Exception as e:
        print(f"[ERROR] Redshift에서 가사 차트 데이터를 가져오는 중 오류 발생: {e}")
        raise HTTPException(status_code=500, detail=f"가사 차트 데이터를 가져오는 중 오류가 발생했습니다: {e}")
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

    if not music_data:
        print(f"[DEBUG] No simple lyrics chart data found for level1={level1}")
        raise HTTPException(status_code=404, detail=f"{level1}에 대한 가사 차트 데이터를 찾을 수 없습니다.")
    
    return music_data

@router.get("/locations/level1", response_model=List[str])
async def get_level1_list():
    conn = None
    level1_list = []
    try:
        conn = get_redshift_connection_internal()
        cursor = conn.cursor()
        query = "SELECT DISTINCT region FROM raw_data.weather_music ORDER BY region;"
        cursor.execute(query)
        results = cursor.fetchall()
        level1_list = [row[0] for row in results]
        print(f"[DEBUG] Fetched {len(level1_list)} level1 regions: {level1_list}")
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"[ERROR] Redshift에서 level1 목록 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=f"Redshift에서 level1 목록 조회 오류: {e}")
    finally:
        if conn:
            conn.close()
    return level1_list

@router.get("/locations/level2", response_model=List[str])
async def get_level2_list(level1_name: str = Query(..., description="조회할 level1 (시/도) 이름")):
    conn = None
    level2_list = []
    if not level1_name:
        raise HTTPException(status_code=400, detail="level1 이름을 제공해야 합니다.")
    try:
        conn = get_redshift_connection_internal()
        cursor = conn.cursor()
        query = "SELECT DISTINCT level2 FROM raw_data.weather_data WHERE level1 = %s ORDER BY level2;"
        cursor.execute(query, (level1_name,))
        results = cursor.fetchall()
        level2_list = [row[0] for row in results]
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Redshift에서 level2 목록 조회 오류: {e}")
    finally:
        if conn:
            conn.close()
    return level2_list
