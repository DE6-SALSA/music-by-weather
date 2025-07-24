import psycopg2
from fastapi import HTTPException
from airflow.providers.postgres.hooks.postgres import PostgresHook

REDSHIFT_CONN_ID = "redshift_conn"

def test_redshift_connection():
    print("\n--- Redshift 연결 테스트 Via PostgresHook ---")
    conn = None
    try:
        hook = PostgresHook(postgres_conn_id=REDSHIFT_CONN_ID)
        conn = hook.get_conn()
        print("✅ Redshift 연결 성공!")

        with conn.cursor() as cur:
            cur.execute("SELECT 1;")
            print(f"✅ 테스트 쿼리 'SELECT 1;' 결과: {cur.fetchone()}")

        try:
            cur.execute("SELECT COUNT(*) FROM raw_data.top_tag5;")
            print(f"✅ raw_data.top_tag5 테이블 존재 및 총 {cur.fetchone()[0]}개 레코드 확인.")
        except Exception as e:
            print(f"❌ raw_data.top_tag5 테이블 확인 중 오류: {e}")

        try:
            cur.execute("SELECT COUNT(*) FROM raw_data.weather_data;")
            print(f"✅ raw_data.weather_data 테이블 존재 및 총 {cur.fetchone()[0]}개 레코드 확인.")
        except Exception as e:
            print(f"ℹ️ raw_data.weather_data 테이블 확인 중 오류 발생: {e}")

    except Exception as e:
        print(f"❌ Redshift 연결 실패: {e}")
    finally:
        if conn:
            conn.close()
            print("--- Redshift 연결 테스트 종료 ---")

def get_redshift_connection_internal():
    try:
        conn = PostgresHook(postgres_conn_id=REDSHIFT_CONN_ID)
        return conn
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Redshift 연결 오류: {e}")
