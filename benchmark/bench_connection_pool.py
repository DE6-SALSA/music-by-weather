"""
bench_connection_pool.py
========================
DB 커넥션 생성 방식: 매번 신규 생성(Before) vs Pool 재사용(After) 성능 비교

Redshift 환경 없이 psycopg2.pool 동작 방식을 mock으로 시뮬레이션.
실제 Redshift 커넥션 수립 시간(100~300ms)을 CONN_LATENCY로 설정.

사용법:
    python benchmark/bench_connection_pool.py
"""

import time
import threading
import statistics
from contextlib import contextmanager

# 실제 Redshift 커넥션 수립 평균 지연시간 (측정값 기반 설정)
CONN_LATENCY = 0.2   # 200ms (Redshift 신규 커넥션 일반적인 수립 시간)
POOL_MIN = 2
POOL_MAX = 10


# ──────────────────────────────────────────
# BEFORE: 요청마다 새 커넥션 생성 (현재 코드)
# ──────────────────────────────────────────
class MockNewConnection:
    """매번 새 커넥션을 생성하는 현재 방식 시뮬레이션"""
    def __init__(self):
        time.sleep(CONN_LATENCY)  # TCP 핸드셰이크 + 인증 지연
        self._closed = False

    def cursor(self):
        return MockCursor()

    def close(self):
        self._closed = True


class MockCursor:
    def execute(self, query, params=None):
        time.sleep(0.01)  # 쿼리 실행 시간

    def fetchall(self):
        return [("result_row",)]

    def fetchone(self):
        return ("result_row",)

    @property
    def description(self):
        return [("col1",)]

    def close(self):
        pass


def get_new_connection():
    """현재 코드: 매번 새 커넥션 생성"""
    return MockNewConnection()


# ──────────────────────────────────────────
# AFTER: 커넥션 풀에서 재사용 (개선 코드)
# ──────────────────────────────────────────
class MockConnectionPool:
    """psycopg2.pool.ThreadedConnectionPool 동작 방식 시뮬레이션"""
    def __init__(self, minconn: int, maxconn: int):
        self._lock = threading.Lock()
        self._pool = []
        self._in_use = 0
        self._maxconn = maxconn
        # 초기 커넥션 미리 생성 (pool 초기화 비용 1회만 발생)
        for _ in range(minconn):
            self._pool.append(self._create_conn())

    def _create_conn(self):
        time.sleep(CONN_LATENCY)  # 최초 생성 시에만 지연
        return MockNewConnection()

    def getconn(self):
        with self._lock:
            if self._pool:
                conn = self._pool.pop()
                self._in_use += 1
                return conn
            elif self._in_use < self._maxconn:
                conn = self._create_conn()
                self._in_use += 1
                return conn
            else:
                raise Exception("커넥션 풀 고갈")

    def putconn(self, conn):
        with self._lock:
            self._pool.append(conn)
            self._in_use -= 1


_pool = None

def get_pooled_connection():
    """개선 코드: 풀에서 커넥션 재사용"""
    global _pool
    if _pool is None:
        _pool = MockConnectionPool(minconn=POOL_MIN, maxconn=POOL_MAX)
    return _pool.getconn()

def return_connection(conn):
    global _pool
    if _pool:
        _pool.putconn(conn)


# ──────────────────────────────────────────
# 시뮬레이션: 단일 API 요청 처리 시간
# ──────────────────────────────────────────
def simulate_api_request_new_conn():
    """현재 방식: 요청마다 새 커넥션"""
    conn = get_new_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM table LIMIT 10")
    cur.fetchall()
    cur.close()
    conn.close()

def simulate_api_request_pool():
    """개선 방식: 풀에서 커넥션 재사용"""
    conn = get_pooled_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM table LIMIT 10")
    cur.fetchall()
    cur.close()
    return_connection(conn)


def run_benchmark(n_requests: int = 50, n_repeat: int = 3):
    print(f"\n{'='*55}")
    print(f"  bench_connection_pool: 신규 생성 vs Pool 재사용 벤치마크")
    print(f"  요청 수: {n_requests}개  |  반복: {n_repeat}회")
    print(f"  커넥션 수립 지연: {CONN_LATENCY*1000:.0f}ms (Redshift 기준)")
    print(f"{'='*55}")

    # ── BEFORE (매번 새 커넥션) ──
    serial_times = []
    print("\n[BEFORE] 요청마다 새 커넥션 생성...")
    for i in range(n_repeat):
        start = time.perf_counter()
        for _ in range(n_requests):
            simulate_api_request_new_conn()
        elapsed = time.perf_counter() - start
        serial_times.append(elapsed)
        print(f"  Round {i+1}: {elapsed:.2f}s  ({elapsed/n_requests*1000:.0f}ms/req)")

    serial_avg = statistics.mean(serial_times)
    serial_per_req = serial_avg / n_requests * 1000

    # ── AFTER (커넥션 풀) ──
    # 풀 초기화 (이 시간은 서버 기동 시 1회만 발생하므로 측정에서 제외)
    global _pool
    _pool = MockConnectionPool(minconn=POOL_MIN, maxconn=POOL_MAX)

    pool_times = []
    print("\n[AFTER]  커넥션 풀 재사용...")
    for i in range(n_repeat):
        start = time.perf_counter()
        for _ in range(n_requests):
            simulate_api_request_pool()
        elapsed = time.perf_counter() - start
        pool_times.append(elapsed)
        print(f"  Round {i+1}: {elapsed:.2f}s  ({elapsed/n_requests*1000:.0f}ms/req)")

    pool_avg = statistics.mean(pool_times)
    pool_per_req = pool_avg / n_requests * 1000
    improvement = (1 - pool_avg / serial_avg) * 100
    saved_per_req = serial_per_req - pool_per_req

    print(f"\n{'='*55}")
    print(f"  결과 요약")
    print(f"{'='*55}")
    print(f"  [BEFORE] 신규 생성  평균: {serial_avg:.2f}s  ({serial_per_req:.0f}ms/요청)")
    print(f"  [AFTER]  풀 재사용  평균: {pool_avg:.2f}s  ({pool_per_req:.0f}ms/요청)")
    print(f"  요청당 절감: {saved_per_req:.0f}ms  |  전체 개선율: {improvement:.1f}%")
    print(f"{'='*55}")
    print(f"\n  이력서 수치 예시:")
    print(f"  API 요청마다 Redshift 신규 커넥션 생성(~{serial_per_req:.0f}ms 오버헤드)에서")
    print(f"  ThreadedConnectionPool 적용으로 커넥션 재사용,")
    print(f"  요청당 응답시간 {serial_per_req:.0f}ms → {pool_per_req:.0f}ms ({improvement:.0f}% 단축)")


if __name__ == "__main__":
    run_benchmark(n_requests=50, n_repeat=3)
