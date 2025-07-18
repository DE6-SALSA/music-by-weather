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
    try:
        conn = get_redshift_connection_internal() 
        cur = conn.cursor()

        query = """
        SELECT pty, reh, rn1, t1h, wsd, sky, weather_condition
        FROM raw_data.weather_data
        WHERE level1 = %s AND level2 = %s
        ORDER BY date DESC, time DESC 
        LIMIT 1;
        """
        cur.execute(query, (level1, level2))
        result = cur.fetchone()

        if result:
            pty, reh, rn1, t1h, wsd, sky, weather_condition = result
            return {
                "temp": t1h,
                "humidity": reh,
                "precipitation": rn1,
                "description": weather_condition,
                "pty": pty,
                "wsd": wsd,
                "sky": sky
            }
        else:
            print(f"Redshift에 {level1} {level2}에 대한 날씨 데이터가 없습니다.")
            return {} 

    except HTTPException as e: 
        raise e
    except psycopg2.Error as e:
        print(f"Redshift에서 날씨 데이터 조회 오류: {e}")
        return {} 
    finally:
        if conn:
            conn.close()

# --- Last.fm API 호출 함수 ---
async def get_lastfm_track_info(artist: str, track: str) -> Dict[str, str]:
    """
    Last.fm API에서 비동기적으로 트랙 정보를 가져온다.
    이미지 URL, 아티스트 URL, 트랙 URL
    """
    async with httpx.AsyncClient() as client:
        params = {
            "method": "track.getInfo",
            "api_key": LASTFM_API_KEY,
            "artist": artist,
            "track": track,
            "format": "json"
        }
        try:
            response = await client.get(LASTFM_API_URL, params=params, timeout=5)
            response.raise_for_status()
            data = response.json()

            result_dict = {"image_url": "", "artist_url": "", "track_url": ""}

            # Last.fm 응답에서 필요한 정보 추출 (기존 로직 동일)
            track_info = data.get("track", {})
            if track_info:
                # 이미지 URL 추출 (다양한 크기 중 'extralarge' 또는 'large' 우선)
                if "album" in track_info and "image" in track_info["album"]:
                    for img in track_info["album"]["image"]:
                        if img.get("size") == "extralarge" and img.get("#text"):
                            result_dict["image_url"] = img["#text"]
                            break
                    if not result_dict["image_url"]: # extralarge가 없으면 large를 시도
                        for img in track_info["album"]["image"]:
                            if img.get("size") == "large" and img.get("#text"):
                                result_dict["image_url"] = img["#text"]
                                break
                
                # 아티스트 URL 및 트랙 URL 추출
                result_dict["artist_url"] = track_info.get("artist", {}).get("url", "")
                result_dict["track_url"] = track_info.get("url", "")
            
            return result_dict

        except httpx.RequestError as e:
            # 네트워크 오류, 타임아웃 등의 요청 관련 오류 처리
            print(f"Last.fm API 호출 오류 (아티스트: {artist}, 트랙: {track}): {e}")
            return {"image_url": "", "artist_url": "", "track_url": ""}
        except httpx.HTTPStatusError as e:
            # 4xx 또는 5xx 응답 상태 코드 오류 처리
            print(f"Last.fm API 응답 오류 (아티스트: {artist}, 트랙: {track}): {e.response.status_code} - {e.response.text}")
            return {"image_url": "", "artist_url": "", "track_url": ""}
        except Exception as e:
            # 그 외 예상치 못한 오류 처리
            print(f"Last.fm API 처리 중 알 수 없는 오류 발생 (아티스트: {artist}, 트랙: {track}): {e}")
            return {"image_url": "", "artist_url": "", "track_url": ""}

# --- Redshift 쿼리 생성 함수 (기존과 동일) ---
def build_redshift_query(weather_condition: Optional[str] = None, tags: Optional[List[str]] = None, search_query: Optional[str] = None, limit: int = 10, randomize: bool = False) -> str:
    """
    Redshift에서 음악 데이터를 가져오기 위한 SQL 쿼리를 생성합니다.
    이 함수는 실제 데이터베이스 스키마와 요구사항에 맞게 수정해야 합니다.
    """
    select_clause = "artist, title, play_cnt, listener_cnt, tag1, tag2, tag3, tag4, tag5"
    base_query = f"SELECT {select_clause} FROM raw_data.top_tag5"
    conditions = [] 
    
    # 이 함수에서는 %s 플레이스홀더만 반환하고, 실제 값은 호출하는 쪽에서 전달합니다.
    # 하지만 현재 Redshift 연동 방식에서는 쿼리 문자열과 파라미터를 따로 처리하므로,
    # build_redshift_query는 쿼리만 반환하고, 파라미터는 별도의 리스트로 구성합니다.
    
    # Note: 여기서는 동기식 psycopg2를 사용하여 파라미터를 그대로 포함하는 방식으로 쿼리 빌딩을 유지합니다.
    # 실제로는 psycopg2의 execute 메서드에 파라미터를 튜플로 넘기는 것이 SQL 인젝션 방지에 더 좋습니다.

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
    music_data = [] # 최종 결과를 담을 리스트

    try:
        conn = get_redshift_connection_internal() 
        cur = conn.cursor()

        full_query = build_redshift_query(weather_condition, tags, search_query, limit, randomize)
        
        print(f"\n[DEBUG] Executing music query:")
        print(f"[DEBUG] Query: {full_query}")
        
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
            
            # Redshift 데이터만 먼저 추가
            music_data.append(music_dict) 
            
            # Last.fm 호출 태스크 추가 (await 없이)
            lastfm_tasks.append(get_lastfm_track_info(music_dict['artist'], music_dict['title']))

        # 모든 Last.fm 태스크 병렬 실행 및 결과 대기
        lastfm_results = await asyncio.gather(*lastfm_tasks)

        # Last.fm 결과를 music_data에 통합
        for i, lastfm_info in enumerate(lastfm_results):
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
        # SQL 인젝션 방지를 위해 플레이스홀더 사용
        query = "SELECT DISTINCT level2 FROM raw_data.weather_data WHERE level1 = %s ORDER BY level2;"
        cursor.execute(query, (level1_name,)) # 파라미터를 튜플로 전달
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


def get_current_weather_from_redshift_internal(level1: str, level2: str) -> Dict[str, Union[str, float, int]]:
    conn = None
    cur = None
    weather_info = {}

    try:
        conn = get_redshift_connection_internal()
        cur = conn.cursor()

        # date (VARCHAR), time (VARCHAR) 컬럼을 사용하여 최신 데이터를 가져오는 쿼리
        # Redshift의 TO_TIMESTAMP 함수를 사용하여 datetime 객체를 생성하고 정렬
        query = """
            SELECT weather_condition, t1h, reh, rn1, pty, wsd, sky
            FROM raw_data.weather_data
            WHERE level1 = %s AND level2 = %s
            ORDER BY date + CAST(time AS TIME) DESC -- DATE + TIME으로 TIMESTAMP 생성
            LIMIT 1;
        """
        
        print(f"[DEBUG] Fetching weather for level1={level1}, level2={level2}")
        cur.execute(query, (level1, level2))
        result = cur.fetchone()

        if result:
            temperature = result[1] # Redshift에서 가져온 t1h 값
            try:
                # 안전하게 float으로 변환 시도. NULL이거나 변환 불가 시 None으로 설정
                temperature = float(temperature) if temperature is not None else None
            except (ValueError, TypeError):
                # 숫자로 변환할 수 없는 경우 (예: 'N/A' 또는 빈 문자열)
                temperature = None 

            weather_info = {
                "description": result[0],
                "temperature": temperature, # 변환된 temperature 사용
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


# --- 3. 날씨 기반 음악 추천 API 엔드포인트 ---
@app.get("/recommend/weather", response_model=List[Dict])
async def recommend_music_by_weather(location: str = "서울특별시", sub_location: Optional[str] = None): 
    # get_current_weather_from_redshift_internal이 동기 함수라면 await 필요 없음.
    weather_info = get_current_weather_from_redshift_internal(location, sub_location if sub_location else "강남구")
    current_condition = weather_info.get("description") 

    if not current_condition: 
        raise HTTPException(status_code=500, detail=f"{location} {sub_location if sub_location else '강남구'}의 날씨 정보를 Redshift에서 가져올 수 없습니다.")

    print(f"날씨 정보: {location}, 조건: {current_condition}") 

    recommended_music = await get_music_data_from_redshift_internal(weather_condition=current_condition)

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
    limit: int = 20
):
    if not query:
        raise HTTPException(status_code=400, detail="검색어를 입력해주세요.")
    
    music_results = await get_music_data_from_redshift_internal(search_query=query, limit=limit) 
    
    if not music_results:
        raise HTTPException(status_code=404, detail=f"'{query}'에 대한 검색 결과를 찾을 수 없습니다.")
    
    return music_results

# --- 5. 차트 순위 조회 API ---
@app.get("/chart_rank", response_model=List[Dict])
async def get_chart_rank(limit: int = 100):
    music_rank_data = []
    conn = None
    cur = None # cur 변수 초기화 추가
    try:
        conn = get_redshift_connection_internal()
        cur = conn.cursor()

        select_clause = "artist, title, play_cnt, listener_cnt, tag1, tag2, tag3, tag4, tag5"

        query = f"""
        SELECT {select_clause}
        FROM raw_data.top_tag5
        ORDER BY load_time DESC
        LIMIT %s;
        """
        cur.execute(query, (limit,))
        music_records = cur.fetchall()

        columns = [desc[0] for desc in cur.description]
        
        lastfm_tasks = [] # Last.fm API 호출 태스크들을 담을 리스트
        
        # Redshift 레코드를 기반으로 기본 music_dict를 만들고 Last.fm 태스크를 준비
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
            music_rank_data.append(music_dict) # 먼저 Redshift 데이터와 rank를 추가

        lastfm_results = await asyncio.gather(*lastfm_tasks)

        for i, lastfm_info in enumerate(lastfm_results):
            music_rank_data[i].update(lastfm_info) 

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

# --- 6. 음악 검색 API ---
@app.get("/search/music", response_model=List[Dict])
async def search_music(
    query: str = Query(..., min_length=2, description="검색할 곡명, 아티스트, 앨범 또는 태그"),
    limit: int = 20
):
    search_results = get_music_data_from_redshift_internal(search_query=query, limit=limit)

    if not search_results:
        raise HTTPException(status_code=404, detail=f"'{query}'에 대한 검색 결과를 찾을 수 없습니다.")
    return search_results

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)