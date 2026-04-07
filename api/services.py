import asyncio
import httpx
from typing import List, Dict, Optional, Union
from fastapi import HTTPException
from db import get_redshift_connection_internal, release_connection
from constants import LASTFM_API_KEY, LASTFM_API_URL

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

    except Exception as e:
        print(f"Redshift에서 날씨 데이터를 가져오는 중 오류 발생: {e}")
    finally:
        if cur:
            cur.close()
        if conn:
            release_connection(conn)
    return weather_info

def build_redshift_query(
    weather_condition: Optional[str] = None,
    tags: Optional[List[str]] = None,
    search_query: Optional[str] = None,
    limit: int = 10,
    randomize: bool = False
) -> tuple:
    """
    SQL Injection 방지를 위해 parameterized query로 구성.
    반환값: (sql_string, params_list)
    호출부에서 cur.execute(sql, params) 형태로 사용.
    """
    select_clause = "artist, title, play_cnt, listener_cnt, tag1, tag2, tag3, tag4, tag5"
    base_query = f"SELECT {select_clause} FROM analytics_data.top_tag5"
    conditions = []
    params = []

    # 사용자 입력 tags 필터 — 각 tag를 %s 플레이스홀더로 바인딩
    if tags:
        tag_conditions = []
        for tag in tags:
            pattern = f"%{tag.lower()}%"
            tag_conditions.append(
                "(LOWER(tag1) LIKE %s OR LOWER(tag2) LIKE %s OR LOWER(tag3) LIKE %s"
                " OR LOWER(tag4) LIKE %s OR LOWER(tag5) LIKE %s)"
            )
            params.extend([pattern] * 5)
        conditions.append("(" + " OR ".join(tag_conditions) + ")")

    # 날씨 조건 — 내부 화이트리스트 맵을 통해 변환 후 %s 바인딩
    if weather_condition:
        weather_to_tags_map = {
            "Clear":   ["happy", "love", "summer", "sunny", "upbeat", "pop", "dance", "fun"],
            "Cloudy":  ["indie", "alternative", "mellow", "chill", "folk", "soft rock"],
            "Rainy":   ["sad song", "heartbreak", "ballad", "melancholic"],
            "Stormy":  ["metal", "hardcore", "emo", "punk", "aggressive"],
            "Snowy":   ["christmas", "winter", "dreamy", "ethereal"],
            "Windy":   ["jazz", "instrumental", "smooth", "airy", "ambient"],
            "Hot":     ["tropical house", "reggaeton", "latin pop", "dancehall"],
            "Cold":    ["dark pop", "coldwave", "gothic", "darkwave"],
        }
        mapped_tags = weather_to_tags_map.get(weather_condition, [])
        if mapped_tags:
            weather_tag_conditions = []
            for tag in mapped_tags:
                pattern = f"%{tag.lower()}%"
                weather_tag_conditions.append(
                    "(LOWER(tag1) LIKE %s OR LOWER(tag2) LIKE %s OR LOWER(tag3) LIKE %s"
                    " OR LOWER(tag4) LIKE %s OR LOWER(tag5) LIKE %s)"
                )
                params.extend([pattern] * 5)
            conditions.append("(" + " OR ".join(weather_tag_conditions) + ")")

    # 검색어 — 직접 입력값이므로 반드시 %s 바인딩
    if search_query:
        pattern = f"%{search_query.lower()}%"
        conditions.append(
            "(LOWER(artist) LIKE %s OR LOWER(title) LIKE %s"
            " OR LOWER(tag1) LIKE %s OR LOWER(tag2) LIKE %s OR LOWER(tag3) LIKE %s"
            " OR LOWER(tag4) LIKE %s OR LOWER(tag5) LIKE %s)"
        )
        params.extend([pattern] * 7)

    full_query = base_query
    if conditions:
        full_query += " WHERE " + " AND ".join(conditions)

    full_query += " ORDER BY " + ("RANDOM()" if randomize else "load_time DESC") + " LIMIT %s"
    params.append(limit)

    return full_query, params

async def get_music_data_from_redshift_internal(
    weather_condition: Optional[str] = None, 
    tags: Optional[List[str]] = None, 
    search_query: Optional[str] = None, 
    limit: int = 10, 
    randomize: bool = False
) -> List[Dict]:
    conn = None
    cur = None
    music_data = []

    try:
        conn = get_redshift_connection_internal() 
        cur = conn.cursor()

        full_query, query_params = build_redshift_query(weather_condition, tags, search_query, limit, randomize)

        print(f"\n[DEBUG] Executing music query: {full_query}")

        cur.execute(full_query, query_params)
        music_records = cur.fetchall()

        print(f"[DEBUG] Number of music records fetched: {len(music_records)}")
        if music_records:
            print(f"[DEBUG] First fetched music record: {music_records[0]}")

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
        print(f"[DEBUG] HTTPException in get_music_data_from_redshift_internal: {e}")
        raise e
    except Exception as e:
        print(f"Redshift에서 음악 데이터를 가져오는 중 오류 발생: {e}")
        return []
    finally:
        if cur:
            cur.close()
        if conn:
            release_connection(conn)
    
    print(f"[DEBUG] Final music_data length: {len(music_data)}")
    return music_data

async def get_lastfm_track_info(artist: str, track: str) -> Dict[str, str]:
    async with httpx.AsyncClient() as client:
        params = {
            "method": "track.getInfo",
            "api_key": LASTFM_API_KEY,
            "artist": artist,
            "track": track,
            "format": "json"
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
