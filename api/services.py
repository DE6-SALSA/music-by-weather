import asyncio
import os
from typing import List, Dict, Optional, Union
import httpx
import psycopg2
from fastapi import HTTPException
from airflow.models import Variable

from db import get_redshift_connection_internal
from constants import WEATHER_TO_TAGS_MAP
from utils import collect_tags


LASTFM_API_KEY ="65c7558dc7abd9c3dc19c3c74b616c21"
LASTFM_API_URL = "http://ws.audioscrobbler.com/2.0/"

# --- 날씨 조회 ---
def get_current_weather_from_redshift_internal(level1: str, level2: str) -> Dict[str, Union[str, float, int]]:
    conn = None
    cur = None
    weather_info = {}
    try:
        conn = get_redshift_connection_internal()
        cur = conn.cursor()
        query = """
            SELECT weather_condition, t1h, reh, rn1, pty, wsd, sky
            FROM raw_data.weather_data
            WHERE level1 = %s AND level2 = %s
            ORDER BY date + CAST(time AS TIME) DESC
            LIMIT 1;
        """
        print(f"[DEBUG] Fetching weather for level1={level1}, level2={level2}")
        cur.execute(query, (level1, level2))
        result = cur.fetchone()

        if result:
            temperature = result[1]
            try:
                temperature = float(temperature) if temperature is not None else None
            except (ValueError, TypeError):
                temperature = None

            weather_info = {
                "description": result[0],
                "temperature": temperature,
                "humidity": result[2],
                "precipitation": result[3],
                "pty": result[4],
                "wsd": result[5],
                "sky": result[6],
            }
            print(f"[DEBUG] Fetched weather info: {weather_info}")
        else:
            print(f"[DEBUG] No weather data found for {level1} {level2}.")

    except psycopg2.Error as e:
        print(f"Redshift에서 날씨 데이터를 가져오는 중 오류 발생: {e}")
    except Exception as e:
        print(f"날씨 데이터를 처리하는 중 알 수 없는 오류 발생: {e}")
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()
    return weather_info

# --- 쿼리 빌더 ---
def build_redshift_query(
    weather_condition: Optional[str] = None,
    tags: Optional[List[str]] = None,
    search_query: Optional[str] = None,
    limit: int = 10,
    randomize: bool = False
) -> str:
    select_clause = "artist, title, play_cnt, listener_cnt, tag1, tag2, tag3, tag4, tag5"
    base_query = f"SELECT {select_clause} FROM raw_data.top_tag5"
    conditions = []

    if tags:
        tag_conditions = []
        for tag in tags:
            tag_conditions.append(
                f"(LOWER(tag1) LIKE '%{tag.lower()}%' OR LOWER(tag2) LIKE '%{tag.lower()}%' OR "
                f"LOWER(tag3) LIKE '%{tag.lower()}%' OR LOWER(tag4) LIKE '%{tag.lower()}%' OR LOWER(tag5) LIKE '%{tag.lower()}%')"
            )
        conditions.append("(" + " OR ".join(tag_conditions) + ")")

    if weather_condition:
        mapped_tags = WEATHER_TO_TAGS_MAP.get(weather_condition, [])
        if mapped_tags:
            weather_tag_conditions = []
            for tag in mapped_tags:
                weather_tag_conditions.append(
                    f"(LOWER(tag1) LIKE '%{tag.lower()}%' OR LOWER(tag2) LIKE '%{tag.lower()}%' OR "
                    f"LOWER(tag3) LIKE '%{tag.lower()}%' OR LOWER(tag4) LIKE '%{tag.lower()}%' OR LOWER(tag5) LIKE '%{tag.lower()}%')"
                )
            conditions.append("(" + " OR ".join(weather_tag_conditions) + ")")

    if search_query:
        search_pattern = f"%{search_query.lower()}%"
        conditions.append(
            f"""
            (
                LOWER(artist) LIKE '{search_pattern}' OR
                LOWER(title) LIKE '{search_pattern}' OR
                LOWER(tag1) LIKE '{search_pattern}' OR
                LOWER(tag2) LIKE '{search_pattern}' OR
                LOWER(tag3) LIKE '{search_pattern}' OR
                LOWER(tag4) LIKE '{search_pattern}' OR
                LOWER(tag5) LIKE '{search_pattern}'
            )
            """
        )

    full_query = base_query
    if conditions:
        full_query += " WHERE " + " AND ".join(conditions)

    full_query += " ORDER BY " + ("RANDOM()" if randomize else "load_time DESC") + f" LIMIT {limit};"
    return full_query

# --- Redshift 음악 데이터 + Last.fm 통합 ---
async def get_music_data_from_redshift_internal(
    weather_condition: Optional[str] = None,
    tags: Optional[List[str]] = None,
    search_query: Optional[str] = None,
    limit: int = 10,
    randomize: bool = False
) -> List[Dict]:
    conn = None
    cur = None
    music_data: List[Dict] = []

    try:
        conn = get_redshift_connection_internal()
        cur = conn.cursor()

        full_query = build_redshift_query(weather_condition, tags, search_query, limit, randomize)
        print(f"\n[DEBUG] Executing music query: {full_query}")
        cur.execute(full_query)
        music_records = cur.fetchall()

        print(f"[DEBUG] Number of music records fetched: {len(music_records)}")
        if music_records:
            print(f"[DEBUG] First fetched music record: {music_records[0]}")

        columns = [desc[0] for desc in cur.description]
        lastfm_tasks = []

        for record in music_records:
            music_dict = dict(zip(columns, record))
            music_dict["tags"] = collect_tags(music_dict)
            for i in range(1, 6):
                music_dict.pop(f"tag{i}", None)
            music_data.append(music_dict)
            lastfm_tasks.append(get_lastfm_track_info(music_dict["artist"], music_dict["title"]))

        lastfm_results = await asyncio.gather(*lastfm_tasks, return_exceptions=True)
        for i, lastfm_info in enumerate(lastfm_results):
            if isinstance(lastfm_info, Exception):
                print(f"[ERROR] Last.fm API call failed for track {i+1}: {music_data[i]['artist']} - {music_data[i]['title']}, Error: {lastfm_info}")
                music_data[i].update({"image_url": "", "artist_url": "", "track_url": ""})
            else:
                music_data[i].update(lastfm_info)

    except HTTPException as e:
        print(f"[DEBUG] HTTPException in get_music_data_from_redshift_internal: {e}")
        raise e
    except psycopg2.Error as e:
        print(f"Redshift에서 음악 데이터를 가져오는 중 오류 발생: {e}")
        return []
    except Exception as e:
        print(f"데이터 가져오는 중 알 수 없는 오류 발생: {e}")
        return []
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

    print(f"[DEBUG] Final music_data length: {len(music_data)}")
    return music_data

# --- Last.fm 호출 ---
async def get_lastfm_track_info(artist: str, track: str) -> Dict[str, str]:
    async with httpx.AsyncClient() as client:
        params = {
            "method": "track.getInfo",
            "api_key": LASTFM_API_KEY,
            "artist": artist,
            "track": track,
            "format": "json",
        }

        try:
            print(f"[DEBUG] Calling Last.fm API for artist: {artist}, track: {track}")
            response = await client.get(LASTFM_API_URL, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()

            result_dict = {"image_url": "", "artist_url": "", "track_url": ""}

            track_info = data.get("track", {})
            if track_info:
                if "album" in track_info and "image" in track_info["album"]:
                    for img in track_info["album"]["image"]:
                        if img.get("size") == "extralarge" and img.get("#text"):
                            result_dict["image_url"] = img["#text"]
                            break
                    if not result_dict["image_url"]:
                        for img in track_info["album"]["image"]:
                            if img.get("size") == "large" and img.get("#text"):
                                result_dict["image_url"] = img["#text"]
                                break

                result_dict["artist_url"] = track_info.get("artist", {}).get("url", "")
                result_dict["track_url"] = track_info.get("url", "")

            print(f"[DEBUG] Last.fm API response for {artist} - {track}: {result_dict}")
            return result_dict

        except httpx.RequestError as e:
            print(f"[ERROR] Last.fm API 호출 오류 (아티스트: {artist}, 트랙: {track}): {e}")
            return {"image_url": "", "artist_url": "", "track_url": ""}
        except httpx.HTTPStatusError as e:
            print(f"[ERROR] Last.fm API 응답 오류 (아티스트: {artist}, 트랙: {track}): {e.response.status_code} - {e.response.text}")
            return {"image_url": "", "artist_url": "", "track_url": ""}
        except Exception as e:
            print(f"[ERROR] Last.fm API 처리 중 알 수 없는 오류 발생 (아티스트: {artist}, 트랙: {track}): {e}")
            return {"image_url": "", "artist_url": "", "track_url": ""}

# --- 서비스 레벨 함수들 (엔드포인트에서 호출) ---
def get_level1_list_service() -> List[str]:
    conn = None
    try:
        conn = get_redshift_connection_internal()
        cursor = conn.cursor()
        query = "SELECT DISTINCT level1 FROM raw_data.weather_data ORDER BY level1;"
        cursor.execute(query)
        results = cursor.fetchall()
        return [row[0] for row in results]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Redshift에서 level1 목록 조회 오류: {e}")
    finally:
        if conn:
            conn.close()

def get_level2_list_service(level1_name: str) -> List[str]:
    if not level1_name:
        raise HTTPException(status_code=400, detail="level1 이름을 제공해야 합니다.")
    conn = None
    try:
        conn = get_redshift_connection_internal()
        cursor = conn.cursor()
        query = "SELECT DISTINCT level2 FROM raw_data.weather_data WHERE level1 = %s ORDER BY level2;"
        cursor.execute(query, (level1_name,))
        results = cursor.fetchall()
        return [row[0] for row in results]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Redshift에서 level2 목록 조회 오류: {e}")
    finally:
        if conn:
            conn.close()

async def recommend_music_by_weather_service(location: str, sub_location: Optional[str], randomize: bool):
    weather_info = get_current_weather_from_redshift_internal(location, sub_location if sub_location else "강남구")
    current_condition = weather_info.get("description")
    if not current_condition:
        raise HTTPException(status_code=500, detail=f"{location} {sub_location or '강남구'} 날씨 정보를 가져올 수 없습니다.")

    print(f"날씨 정보: {location}, 조건: {current_condition}")
    recommended_music = await get_music_data_from_redshift_internal(weather_condition=current_condition, randomize=randomize)

    if not recommended_music:
        fallback_music = await get_music_data_from_redshift_internal(limit=5)
        if not fallback_music:
            return [{"message": f"{location}의 {current_condition} 날씨에 맞는 추천 음악이 없습니다. DB에 데이터가 부족합니다."}]
        return [{"message": f"{location}의 {current_condition} 날씨에 맞는 추천 음악을 찾을 수 없습니다. 다른 인기 음악을 추천합니다."}, *fallback_music]

    return recommended_music

async def search_music_service(query: str, limit: int, randomize: bool):
    if not query:
        raise HTTPException(status_code=400, detail="검색어를 입력해주세요.")
    music_results = await get_music_data_from_redshift_internal(search_query=query, limit=limit, randomize=randomize)
    if not music_results:
        raise HTTPException(status_code=404, detail=f"'{query}'에 대한 검색 결과를 찾을 수 없습니다.")
    return music_results

async def get_chart_rank_service(limit: int):
    music_rank_data: List[Dict] = []
    conn = None
    cur = None
    try:
        conn = get_redshift_connection_internal()
        cur = conn.cursor()
        select_clause = "artist, title, play_cnt, listener_cnt, tag1, tag2, tag3, tag4, tag5"
        query = f"""
        SELECT {select_clause}
        FROM raw_data.top_tag5
        ORDER BY play_cnt DESC, listener_cnt DESC
        LIMIT %s;
        """
        cur.execute(query, (limit,))
        music_records = cur.fetchall()

        print(f"[DEBUG] Number of chart rank records fetched: {len(music_records)}")
        if music_records:
            print(f"[DEBUG] First chart rank record: {music_records[0]}")

        columns = [desc[0] for desc in cur.description]
        lastfm_tasks = []

        for i, record in enumerate(music_records):
            music_dict = dict(zip(columns, record))
            music_dict["tags"] = collect_tags(music_dict)
            for j in range(1, 6):
                music_dict.pop(f"tag{j}", None)
            music_dict["rank"] = i + 1

            lastfm_tasks.append(get_lastfm_track_info(music_dict["artist"], music_dict["title"]))
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
    except psycopg2.Error as e:
        print(f"Redshift에서 차트 순위 데이터를 가져오는 중 오류 발생: {e}")
        raise HTTPException(status_code=500, detail="차트 순위 데이터 오류")
    except Exception as e:
        print(f"알 수 없는 오류 발생 (get_chart_rank): {e}")
        raise HTTPException(status_code=500, detail="알 수 없는 서버 오류")
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

    if not music_rank_data:
        raise HTTPException(status_code=404, detail="차트 순위 데이터를 찾을 수 없습니다.")
    return music_rank_data
