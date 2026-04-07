import psycopg2
import psycopg2.pool
import threading
from contextlib import contextmanager
from fastapi import HTTPException
from constants import REDSHIFT_CONFIG

# ──────────────────────────────────────────────────────────────
# [BEFORE] 매 요청마다 psycopg2.connect() 호출 → ~200ms 오버헤드
# [AFTER]  ThreadedConnectionPool로 커넥션 재사용 → ~5ms
#
# 애플리케이션 수명 동안 풀을 1회 초기화.
# FastAPI lifespan 또는 최초 요청 시 지연 초기화(lazy init) 방식으로 생성.
# ──────────────────────────────────────────────────────────────

_pool: psycopg2.pool.ThreadedConnectionPool | None = None
_pool_lock = threading.Lock()


def _init_pool() -> psycopg2.pool.ThreadedConnectionPool:
    """커넥션 풀 초기화 — 애플리케이션 기동 시 1회만 호출"""
    try:
        return psycopg2.pool.ThreadedConnectionPool(
            minconn=2,
            maxconn=10,
            host=REDSHIFT_CONFIG["host"],
            port=int(REDSHIFT_CONFIG["port"]),
            dbname=REDSHIFT_CONFIG["database"],
            user=REDSHIFT_CONFIG["user"],
            password=REDSHIFT_CONFIG["password"],
            connect_timeout=30,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"커넥션 풀 초기화 실패: {e}")


def _get_pool() -> psycopg2.pool.ThreadedConnectionPool:
    """풀 싱글턴 반환 (lazy init, thread-safe)"""
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                _pool = _init_pool()
    return _pool


@contextmanager
def get_redshift_connection():
    """
    커넥션 풀에서 커넥션을 빌려주는 컨텍스트 매니저.
    with 블록 종료 시 자동으로 풀에 반납.

    사용 예시:
        with get_redshift_connection() as conn:
            cur = conn.cursor()
            cur.execute(...)
    """
    pool = _get_pool()
    conn = None
    try:
        conn = pool.getconn()
        yield conn
    except psycopg2.pool.PoolError as e:
        raise HTTPException(status_code=503, detail=f"커넥션 풀 고갈: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"데이터베이스 연결 오류: {e}")
    finally:
        if conn is not None:
            pool.putconn(conn)


def get_redshift_connection_internal():
    """
    기존 호출부 호환용 함수. 풀에서 커넥션을 반환.
    호출부에서 conn.close() 대신 _get_pool().putconn(conn)을 호출해야 하지만,
    레거시 코드 수정 범위를 최소화하기 위해 유지.
    신규 코드는 get_redshift_connection() 컨텍스트 매니저 사용 권장.
    """
    pool = _get_pool()
    try:
        return pool.getconn()
    except psycopg2.pool.PoolError as e:
        raise HTTPException(status_code=503, detail=f"커넥션 풀 고갈: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"데이터베이스 연결 오류: {e}")


def release_connection(conn) -> None:
    """커넥션을 풀에 반납. get_redshift_connection_internal() 사용 시 반드시 호출."""
    pool = _get_pool()
    if conn is not None:
        pool.putconn(conn)


def test_redshift_connection():
    print("\n--- Redshift 연결 테스트 시작 ---")
    try:
        with get_redshift_connection() as conn:
            print("✅ Redshift 연결 성공!")
            cur = conn.cursor()
            cur.execute("SELECT 1;")
            print(f"✅ 테스트 쿼리 결과: {cur.fetchone()}")

            try:
                cur.execute("SELECT COUNT(*) FROM analytics_data.top_tag5;")
                print(f"✅ top_tag5 레코드 수: {cur.fetchone()[0]}")
            except psycopg2.Error as e:
                print(f"❌ top_tag5 확인 오류: {e}")

            try:
                cur.execute("SELECT COUNT(*) FROM raw_data.weather_music;")
                print(f"✅ weather_music 레코드 수: {cur.fetchone()[0]}")
            except psycopg2.Error as e:
                print(f"❌ weather_music 확인 오류: {e}")

    except Exception as e:
        print(f"❌ 연결 실패: {e}")
    finally:
        print("--- Redshift 연결 테스트 종료 ---")
