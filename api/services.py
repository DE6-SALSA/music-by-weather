import asyncio
import httpx
from typing import List, Dict, Optional, Union
from fastapi import HTTPException
from .db import get_redshift_connection_internal # Redshift 연결 함수를 임포트합니다.
# get_postgres_connection_internal 대신 get_redshift_connection_internal을 사용합니다.


async def get_current_weather_from_redshift_internal(level1: str, level2: str) -> Dict[str, Union[str, float, int]]:
    """
    Redshift에서 현재 날씨 데이터를 가져오는 함수.
    """
    conn = None
    cur = None
    weather_info = {}

    try:
        # get_postgres_connection_internal() 대신 get_redshift_connection_internal() 호출
        conn = get_redshift_connection_internal()
        cur = conn.cursor()

        query = """
            SELECT weather_condition, t1h, reh, rn1, pty, wsd, sky
            FROM raw_data.weather_data -- Redshift에 맞는 스키마와 테이블명 확인
            WHERE level1 = %s AND level2 = %s
            ORDER BY date + CAST(time AS TIME) DESC
            LIMIT 1;
        """

        print(f"[DEBUG] Fetching weather for level1={level1}, level2={level2} from Redshift")
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
            print(f"[DEBUG] Fetched weather info from Redshift: {weather_info}")
        else:
            print(f"[DEBUG] No weather data found in Redshift for {level1} {level2}.")

    except Exception as e:
        print(f"Redshift에서 날씨 데이터를 가져오는 중 오류 발생: {e}") # 메시지 수정
        raise HTTPException(status_code=500, detail=f"Redshift에서 날씨 데이터 조회 오류: {e}") # 에러 메시지 수정
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()
    return weather_info

def build_redshift_query(weather_condition: Optional[str] = None, tags: Optional[List[str]] = None, search_query: Optional[str] = None, limit: int = 10, randomize: bool = False) -> str:
    """
    Redshift 쿼리를 생성하는 함수.
    """
    select_clause = "artist, title, play_cnt, listener_cnt, tag1, tag2, tag3, tag4, tag5"
    base_query = f"SELECT {select_clause} FROM raw_data.top_tag5" # Redshift에 맞는 스키마와 테이블명 확인
    conditions = []

    if tags:
        tag_conditions = []
        for tag in tags:
            tag_conditions.append(
                f"(LOWER(tag1) LIKE '%{tag.lower()}%' OR LOWER(tag2) LIKE '%{tag.lower()}%' OR LOWER(tag3) LIKE '%{tag.lower()}%' OR LOWER(tag4) LIKE '%{tag.lower()}%' OR LOWER(tag5) LIKE '%{tag.lower()}%')"
            )
        conditions.append("(" + " OR ".join(tag_conditions) + ")")

    if weather_condition:
        from .constants import WEATHER_TO_TAGS_MAP  # Import here to avoid circular dependency
        mapped_tags = WEATHER_TO_TAGS_MAP.get(weather_condition, [])

        if mapped_tags:
            weather_tag_conditions = []
            for tag in mapped_tags:
                weather_tag_conditions.append(
                    f"(LOWER(tag1) LIKE '%{tag.lower()}%' OR LOWER(tag2) LIKE '%{tag.lower()}%' OR LOWER(tag3) LIKE '%{tag.lower()}%' OR LOWER(tag4) LIKE '%{tag.lower()}%' OR LOWER(tag5) LIKE '%{tag.lower()}%')"
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

    # Redshift는 RANDOM() 대신 RANDOM() * (max_value - min_value) + min_value 또는 NEWID()를 사용할 수 있지만
    # 여기서는 간단히 ORDER BY RAND() (PostgreSQL 호환) 또는 ORDER BY RANDOM()을 가정.
    # Redshift의 경우: ORDER BY RANDOM() 또는 적절한 랜덤 함수 사용 (데이터 크기에 따라 성능 문제 발생 가능)
    full_query += " ORDER BY " + ("RANDOM()" if randomize else "load_time DESC") + f" LIMIT {limit};"
    # load_time DESC는 Redshift에 해당 컬럼이 있는지 확인 필요.
    # Redshift에서는 ORDER BY RANDOM()이 더 적절할 수 있습니다.

    return full_query


async def get_music_data_from_redshift_internal( # 함수 이름 변경
    weather_condition: Optional[str] = None,
    tags: Optional[List[str]] = None,
    search_query: Optional[str] = None,
    limit: int = 10,
    randomize: bool = False
) -> List[Dict]:
    """
    Redshift에서 음악 데이터를 가져오는 함수.
    """
    conn = None
    cur = None
    music_data = []

    try:
        # get_postgres_connection_internal() 대신 get_redshift_connection_internal() 호출
        conn = get_redshift_connection_internal()
        cur = conn.cursor()

        # build_postgres_query 대신 build_redshift_query 호출
        full_query = build_redshift_query(weather_condition, tags, search_query, limit, randomize)

        print(f"\n[DEBUG] Executing music query on Redshift: {full_query}")

        cur.execute(full_query)
        music_records = cur.fetchall()

        print(f"[DEBUG] Number of music records fetched from Redshift: {len(music_records)}")
        if music_records:
            print(f"[DEBUG] First fetched music record from Redshift: {music_records[0]}")

        columns = [desc[0] for desc in cur.description]

        lastfm_tasks = []

        for record in music_records:
            music_dict = dict(zip(columns, record))

            combined_tags = [
                music_dict[f'tag{i}'] for i in range(1, 6)
                if music_dict.get(f'tag{i}') and music_dict[f'tag{i}'].strip() != ''
            ]
            music_dict['tags'] = combined_tags
            for i in range(1, 6):
                if f'tag{i}' in music_dict:
                    del music_dict[f'tag{i}']

            music_data.append(music_dict)

            lastfm_tasks.append(get_lastfm_track_info(music_dict['artist'], music_dict['title']))

        lastfm_results = await asyncio.gather(*lastfm_tasks, return_exceptions=True)

        for i, lastfm_info in enumerate(lastfm_results):
            if isinstance(lastfm_info, Exception):
                print(f"[ERROR] Last.fm API call failed for track {i+1}: {music_data[i]['artist']} - {music_data[i]['title']}, Error: {lastfm_info}")
                music_data[i].update({"image_url": "", "artist_url": "", "track_url": ""})
            else:
                music_data[i].update(lastfm_info)

    except HTTPException as e:
        print(f"[DEBUG] HTTPException in get_music_data_from_redshift_internal: {e}") # 메시지 수정
        raise e
    except Exception as e:
        print(f"Redshift에서 음악 데이터를 가져오는 중 오류 발생: {e}") # 메시지 수정
        return []
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

    print(f"[DEBUG] Final music_data length: {len(music_data)}")
    return music_data

# get_lastfm_track_info 함수는 그대로 유지됩니다.
async def get_lastfm_track_info(artist: str, track: str) -> Dict[str, str]:
    # ... (기존 코드와 동일)
    async with httpx.AsyncClient() as client:
        params = {
            "method": "track.getInfo",
            "api_key": "YOUR_LASTFM_API_KEY", # 여기에 실제 Last.fm API 키를 넣어야 합니다.
            "artist": artist,
            "track": track,
            "format": "json"
        }
        try:
            print(f"[DEBUG] Calling Last.fm API for artist: {artist}, track: {track}")
            response = await client.get(f"http://ws.audioscrobbler.com/2.0/", params=params, timeout=15) # LASTFM_API_URL 대신 직접 URL 사용
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