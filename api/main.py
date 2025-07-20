import os
import psycopg2
import asyncio
import httpx

from typing import List, Dict, Optional, Union
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv() # .env 파일 로드

app = FastAPI(
    title="Music & Weather Recommendation API",
    description="날씨 정보와 사용자 태그를 기반으로 음악을 추천하는 API",
    version="0.1.0",
)

# --- CORS 설정 ---
origins = [
    "http://localhost",
    "http://localhost:8501", 
    "http://127.0.0.1:8501",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"], 
    allow_headers=["*"], 
)

# --- Redshift 연결 설정 (환경 변수에서 로드) ---
REDSHIFT_CONFIG = {
    "host": os.environ.get("REDSHIFT_HOST"),
    "port": os.environ.get("REDSHIFT_PORT"),
    "database": os.environ.get("REDSHIFT_DBNAME"),
    "user": os.environ.get("REDSHIFT_USER"),
    "password": os.environ.get("REDSHIFT_PASSWORD")
}

# --- Last.fm API 설정 ---
LASTFM_API_KEY = os.environ.get("LASTFM_API_KEY")
LASTFM_API_URL = "http://ws.audioscrobbler.com/2.0/"

# --- 디버깅용 Redshift 연결 테스트 함수 ---
def test_redshift_connection():
    print("\n--- Redshift 연결 테스트 시작 ---")
    conn = None
    try:
        if not all(value for key, value in REDSHIFT_CONFIG.items() if key != "password"):
            print("❌ Redshift 연결 환경 변수(Host, Port, DBNAME, User) 중 일부가 설정되지 않았습니다.")
            print(".env 파일을 확인하거나, REDSHIFT_CONFIG의 값들이 None이 아닌지 확인하세요.")
            raise ValueError("환경 변수 설정 오류")

        redshift_port = int(REDSHIFT_CONFIG["port"])

        conn = psycopg2.connect(
            host=REDSHIFT_CONFIG["host"],
            port=redshift_port,
            dbname=REDSHIFT_CONFIG["database"],
            user=REDSHIFT_CONFIG["user"],
            password=REDSHIFT_CONFIG["password"]
        )
        print("✅ Redshift 연결 성공!")
        
        cur = conn.cursor()
        cur.execute("SELECT 1;")
        result = cur.fetchone()
        print(f"✅ 테스트 쿼리 'SELECT 1;' 결과: {result}")
        
        try:
            cur.execute("SELECT COUNT(*) FROM raw_data.top_tag5;")
            count = cur.fetchone()[0]
            print(f"✅ raw_data.top_tag5 테이블 존재 및 총 {count}개 레코드 확인.")
        except psycopg2.Error as e:
            print(f"❌ raw_data.top_tag5 테이블 확인 중 오류: {e}")

        try:
            cur.execute("SELECT COUNT(*) FROM raw_data.weather_data;")
            count = cur.fetchone()[0]
            print(f"✅ raw_data.weather_data 테이블 존재 및 총 {count}개 레코드 확인.")
        except psycopg2.Error as e:
            print(f"ℹ️ raw_data.weather_data 테이블 확인 중 오류 발생 (아직 데이터가 없을 수 있음): {e}")

    except ValueError as e:
        print(f"❌ Redshift 설정 오류: {e}")
        print("Redshift PORT는 숫자여야 합니다. .env 파일을 확인하세요.")
    except psycopg2.Error as e:
        print(f"❌ Redshift 연결 실패: {e}")
        print("Redshift 설정 (host, port, database, user, password) 또는 네트워크/보안 그룹 설정을 확인해주세요.")
    finally:
        if conn:
            conn.close()
            print("--- Redshift 연결 테스트 종료 ---")

# --- FastAPI 애플리케이션 시작 시 연결 테스트 실행 ---
@app.on_event("startup")
async def startup_event():
    test_redshift_connection()

# --- Redshift 연결 함수 (내부 사용) ---
def get_redshift_connection_internal():
    try:
        redshift_port = int(REDSHIFT_CONFIG["port"])
        
        conn = psycopg2.connect(
            host=REDSHIFT_CONFIG["host"],
            port=redshift_port,
            dbname=REDSHIFT_CONFIG["database"],
            user=REDSHIFT_CONFIG["user"],
            password=REDSHIFT_CONFIG["password"],
            connect_timeout=30,
        )
        return conn
    except ValueError:
        raise HTTPException(status_code=500, detail="Redshift PORT 환경 변수가 유효한 숫자가 아닙니다. .env 파일을 확인해주세요.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"데이터베이스 연결 오류: {e}. .env 파일 및 Redshift 설정을 확인해주세요.")

# --- 1. 날씨 데이터 AWS Redshift에서 가져오기 (내부 함수 유지) ---
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

@app.get("/weather/current", response_model=Dict[str, Union[str, float, int]]) 
async def get_current_weather(level1: str = Query(..., description="시/도 이름"), level2: str = Query(..., description="시/군/구 이름")):
    weather_info = get_current_weather_from_redshift_internal(level1, level2)
    if not weather_info:
        raise HTTPException(status_code=404, detail=f"{level1} {level2}에 대한 날씨 정보를 찾을 수 없습니다.")
    return weather_info

# --- Redshift 쿼리 생성 함수 ---
def build_redshift_query(weather_condition: Optional[str] = None, tags: Optional[List[str]] = None, search_query: Optional[str] = None, limit: int = 10, randomize: bool = False) -> str:
    select_clause = "artist, title, play_cnt, listener_cnt, tag1, tag2, tag3, tag4, tag5"
    base_query = f"SELECT {select_clause} FROM raw_data.top_tag5"
    conditions = [] 
    
    if tags:
        tag_conditions = []
        for tag in tags:
            tag_conditions.append(
                f"(LOWER(tag1) LIKE '%{tag.lower()}%' OR LOWER(tag2) LIKE '%{tag.lower()}%' OR LOWER(tag3) LIKE '%{tag.lower()}%' OR LOWER(tag4) LIKE '%{tag.lower()}%' OR LOWER(tag5) LIKE '%{tag.lower()}%')"
            )
        conditions.append("(" + " OR ".join(tag_conditions) + ")")

    if weather_condition:
        weather_to_tags_map = {
            "Clear": [
                "happy", "love", "summer", "sunny", "upbeat", "pop", "dance", "fun",
                "pop punk", "twerk anthem", "teen pop", "happy dance", "love anthem",
                "party music", "catchy as fuck", "dance-pop", "pop rock", "pop-rap",
                "sunshine pop", "reggaeton", "dancehall", "summer hits", "banger",
                "samba", "party", "uplifting", "pop perfection", "disco pop",
                "danceable", "good vibes"
            ],
            "Cloudy": [
                "indie", "alternative", "mellow", "chill", "folk", "soft rock",
                "indie pop", "indie folk", "indie rock", "chillwave", "dream pop",
                "post-rock", "singer-songwriter", "jangle pop", "folk rock",
                "alternative dance", "twee pop", "chillout", "cloudy pop", "surf rock"
            ],
            "Rainy": [
                "sad song", "heartbreak", "ballad", "melancholic", "crying my eyes out",
                "tear-jerker", "bittersweet", "heartbreakingly beautiful", "sadcore",
                "sad girl", "songs to cry to", "breakup", "regret", "despondency",
                "longing", "yearning", "cryingggg"
            ],
            "Stormy": [
                "metal", "hardcore", "emo", "punk", "aggressive", "screamo", "deathcore",
                "death metal", "black metal", "heavy metal", "thrash metal",
                "grindcore", "nu-metal", "noise rock", "sludge metal", "hardcore punk",
                "dark plugg", "violent"
            ],
            "Snowy": [
                "christmas", "winter", "dreamy", "ethereal", "ambient pop", "dreamy pop",
                "snowy", "icy"
            ],
            "Windy": [
                "jazz", "instrumental", "smooth", "airy", "ambient", "jazz fusion",
                "smooth jazz", "ambient dub", "jazz rap", "acid jazz", "bossa nova",
                "instrumental hip hop", "lounge", "easy listening", "cinematic",
                "chill jazz", "chamber jazz", "piano jazz", "flute", "acoustic instrumental"
            ],
            "Hot": [
                "tropical house", "reggaeton", "baile funk", "dembow", "summer hits",
                "samba rock", "samba de raiz", "latin pop", "dancehall", "moombahton",
                "tropical", "caliente", "hot", "afrobeat", "afropiano"
            ],
            "Cold": [
                "dark pop", "coldwave", "gothic", "darkwave", "industrial", "icy",
                "dark ambient", "witch house", "blackgaze", "depressive black metal"
            ]
        }
        
        mapped_tags = weather_to_tags_map.get(weather_condition, [])
        
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
    
    full_query += " ORDER BY " + ("RANDOM()" if randomize else "load_time DESC") + f" LIMIT {limit};"
    
    return full_query

# --- 2. AWS Redshift 음악 데이터 가져오기 (비동기 Last.fm 통합) ---
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

# --- Last.fm API 호출 함수 ---
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
            response = await client.get(LASTFM_API_URL, params=params, timeout=15)  # 타임아웃 10초 -> 15초
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

# --- 새로운 엔드포인트: level1 목록 가져오기 ---
@app.get("/locations/level1", response_model=List[str])
async def get_level1_list():
    conn = None
    level1_list = []
    try:
        conn = get_redshift_connection_internal()
        cursor = conn.cursor()
        query = "SELECT DISTINCT level1 FROM raw_data.weather_data ORDER BY level1;"
        cursor.execute(query)
        results = cursor.fetchall()
        level1_list = [row[0] for row in results]
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Redshift에서 level1 목록 조회 오류: {e}")
    finally:
        if conn:
            conn.close()
    return level1_list

# --- 새로운 엔드포인트: level2 목록 가져오기 ---
@app.get("/locations/level2", response_model=List[str])
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

# --- 3. 날씨 기반 음악 추천 API 엔드포인트 ---
@app.get("/recommend/weather", response_model=List[Dict])
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

# --- 4. 태그 기반 음악 검색 API 엔드포인트 ---
@app.get("/search/music", response_model=List[Dict], tags=["Music Search"]) 
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

# --- 5. 차트 순위 조회 API ---
@app.get("/chart_rank", response_model=List[Dict])
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
    except psycopg2.Error as e:
        print(f"Redshift에서 차트 순위 데이터를 가져오는 중 오류 발생: {e}")
        raise HTTPException(status_code=500, detail="차트 순위 데이터를 가져오는 중 오류가 발생했습니다.")
    except Exception as e:
        print(f"알 수 없는 오류 발생 (get_chart_rank): {e}")
        raise HTTPException(status_code=500, detail="알 수 없는 서버 오류가 발생했습니다.")
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()
    
    if not music_rank_data:
        raise HTTPException(status_code=404, detail="차트 순위 데이터를 찾을 수 없습니다.")

    return music_rank_data

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)