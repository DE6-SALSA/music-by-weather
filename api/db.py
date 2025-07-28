import psycopg2
import os
from fastapi import HTTPException
from constants import REDSHIFT_CONFIG

def test_redshift_connection():
    print("\n--- Redshift 연결 테스트 시작 ---")
    conn = None
    try:
        if not all(value for key, value in REDSHIFT_CONFIG.items() if key != "password"):
            print("❌ Redshift 연결 환경 변수(Host, Port, DBNAME, User) 중 일부가 설정되지 않았습니다.")
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
            cur.execute("SELECT COUNT(*) FROM analytics_data.top_tag5;")
            count = cur.fetchone()[0]
            print(f"✅ analytics_data.top_tag5 테이블 존재 및 총 {count}개 레코드 확인.")
        except psycopg2.Error as e:
            print(f"❌ analytics_data.top_tag5 테이블 확인 중 오류: {e}")

        try:
            cur.execute("SELECT COUNT(*) FROM raw_data.weather_music;")
            count = cur.fetchone()[0]
            print(f"✅ raw_data.weather_music 테이블 존재 및 총 {count}개 레코드 확인.")
        except psycopg2.Error as e:
            print(f"❌ raw_data.weather_music 테이블 확인 중 오류: {e}")

    except ValueError as e:
        print(f"❌ Redshift 설정 오류: {e}")
    except psycopg2.Error as e:
        print(f"❌ Redshift 연결 실패: {e}")
    finally:
        if conn:
            conn.close()
            print("--- Redshift 연결 테스트 종료 ---")

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
        raise HTTPException(status_code=500, detail="Redshift PORT 환경 변수가 유효한 숫자가 아닙니다.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"데이터베이스 연결 오류: {e}")
