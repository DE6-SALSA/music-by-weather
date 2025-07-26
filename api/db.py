
import psycopg2
from fastapi import HTTPException

# Airflow 메타데이터 DB 설정 (EC2 환경에 맞게 조정 가능)
AIRFLOW_DB_HOST = "localhost"  # Airflow DB가 EC2에 설치된 경우
AIRFLOW_DB_PORT = 5432
AIRFLOW_DB_NAME = "airflow"
AIRFLOW_DB_USER = "airflow"
AIRFLOW_DB_PASSWORD = "airflow"

POSTGRES_CONN_ID = "postgres_conn"  # Airflow에서 PostgreSQL 연결 ID

def get_postgres_credentials_from_airflow():
    try:
        airflow_conn = psycopg2.connect(
            host=AIRFLOW_DB_HOST,
            port=AIRFLOW_DB_PORT,
            dbname=AIRFLOW_DB_NAME,
            user=AIRFLOW_DB_USER,
            password=AIRFLOW_DB_PASSWORD
        )
        cursor = airflow_conn.cursor()
        query = """
        SELECT host, port, login, password, schema, api_url
        FROM connection
        WHERE conn_id = %s
        LIMIT 1;
        """
        cursor.execute(query, (POSTGRES_CONN_ID,))
        result = cursor.fetchone()
        cursor.close()
        airflow_conn.close()

        if result is None:
            raise Exception(f"Connection ID '{POSTGRES_CONN_ID}' not found in Airflow metadata DB.")

        host, port, login, password, schema, api_url = result
        return {
            "host": host,
            "port": port or 5432,
            "user": login,
            "password": password,
            "dbname": schema,
            "api_url": api_url or "http://10.0.45.211:8000"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Airflow connection 조회 실패: {e}")

def get_postgres_connection_internal():
    """
    PostgreSQL 연결을 생성하여 반환.
    """
    try:
        creds = get_postgres_credentials_from_airflow()
        conn = psycopg2.connect(
            host=creds["host"],
            port=int(creds["port"]),
            dbname=creds["dbname"],
            user=creds["user"],
            password=creds["password"],
            connect_timeout=30
        )
        return conn
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PostgreSQL 연결 오류: {e}")

def test_postgres_connection():
    """
    PostgreSQL 연결 테스트 및 테이블 확인.
    """
    print("\n--- PostgreSQL 연결 테스트 via Airflow metadata DB ---")
    conn = None
    try:
        conn = get_postgres_connection_internal()
        print("✅ PostgreSQL 연결 성공!")

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
                print(f"❌ raw_data.weather_data 테이블 확인 중 오류: {e}")

    except Exception as e:
        print(f"❌ PostgreSQL 연결 실패: {e}")
    finally:
        if conn:
            conn.close()
            print("--- PostgreSQL 연결 테스트 종료 ---")
