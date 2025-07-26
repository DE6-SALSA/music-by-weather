import psycopg2
from fastapi import HTTPException

# Airflow 메타데이터 DB 설정
AIRFLOW_DB_HOST = "postgres"
AIRFLOW_DB_PORT = 5432
AIRFLOW_DB_NAME = "airflow"
AIRFLOW_DB_USER = "airflow"
AIRFLOW_DB_PASSWORD = "airflow"

REDSHIFT_CONN_ID = "redshift_conn"

def get_redshift_credentials_from_airflow():
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
        SELECT host, port, login, password, schema
        FROM connection
        WHERE conn_id = %s
        LIMIT 1;
        """
        cursor.execute(query, (REDSHIFT_CONN_ID,))
        result = cursor.fetchone()
        cursor.close()
        airflow_conn.close()

        if result is None:
            raise Exception(f"Connection ID '{REDSHIFT_CONN_ID}' not found in Airflow metadata DB.")

        host, port, login, password, schema = result
        return {
            "host": host,
            "port": port or 5439,
            "user": login,
            "password": password,
            "dbname": schema
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Airflow connection 조회 실패: {e}")

def get_redshift_connection_internal():
    try:
        creds = get_redshift_credentials_from_airflow()
        conn = psycopg2.connect(**creds)
        return conn
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Redshift 연결 오류: {e}")

def test_redshift_connection():
    print("\n--- Redshift 연결 테스트 via Airflow metadata DB ---")
    conn = None
    try:
        conn = get_redshift_connection_internal()
        print("Redshift 연결 성공!")

        with conn.cursor() as cur:
            cur.execute("SELECT 1;")
            print(f"테스트 쿼리 'SELECT 1;' 결과: {cur.fetchone()}")

            try:
                cur.execute("SELECT COUNT(*) FROM raw_data.top_tag5;")
                print(f"✅ raw_data.top_tag5 테이블 존재 및 총 {cur.fetchone()[0]}개 레코드 확인.")
            except Exception as e:
                print(f"top_tag5 테이블 확인 중 오류: {e}")

            try:
                cur.execute("SELECT COUNT(*) FROM raw_data.weather_data;")
                print(f"raw_data.weather_data 테이블 존재 및 총 {cur.fetchone()[0]}개 레코드 확인.")
            except Exception as e:
                print(f"ℹweather_data 테이블 확인 중 오류 발생: {e}")

    except Exception as e:
        print(f"Redshift 연결 실패: {e}")
    finally:
        if conn:
            conn.close()
            print("--- Redshift 연결 테스트 종료 ---")
