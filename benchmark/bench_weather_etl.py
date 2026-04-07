"""
bench_weather_etl.py
====================
fetch_weather_data: 직렬(Before) vs 병렬(After) 기상청 API 호출 성능 비교

실제 API 키가 있으면 USE_REAL_API=True로 변경.
없으면 mock 모드로 실행 (API 지연 시간을 0.5s로 시뮬레이션).

사용법:
    # mock 모드 (기본)
    python benchmark/bench_weather_etl.py

    # 실제 API 모드
    export WEATHER_API_KEY=your_key
    USE_REAL_API=true python benchmark/bench_weather_etl.py
"""

import os
import time
import requests
import concurrent.futures
import statistics
from urllib.parse import urlencode

API_KEY = os.environ.get("WEATHER_API_KEY", "")
USE_REAL_API = os.environ.get("USE_REAL_API", "false").lower() == "true"
BASE_URL = "https://apihub.kma.go.kr/api/typ02/openApi/VilageFcstInfoService_2.0/getUltraSrtFcst"

# 전국 주요 지역 샘플 (nx, ny 격자 좌표)
SAMPLE_REGIONS = [
    ("서울특별시", "강남구",   61, 125),
    ("서울특별시", "종로구",   60, 127),
    ("서울특별시", "마포구",   59, 127),
    ("부산광역시", "해운대구", 99,  76),
    ("부산광역시", "남구",     98,  75),
    ("인천광역시", "남동구",   54, 125),
    ("대구광역시", "중구",     89,  90),
    ("광주광역시", "북구",     58,  74),
    ("대전광역시", "유성구",   67, 100),
    ("울산광역시", "남구",    102,  84),
    ("경기도",     "수원시",   60, 121),
    ("경기도",     "성남시",   62, 123),
    ("경기도",     "고양시",   57, 128),
    ("경기도",     "부천시",   56, 125),
    ("강원도",     "춘천시",   73, 130),
    ("충청북도",   "청주시",   69, 107),
    ("충청남도",   "천안시",   63, 110),
    ("전라북도",   "전주시",   63,  89),
    ("전라남도",   "광양시",   74,  72),
    ("경상북도",   "포항시",  102,  94),
]

MOCK_LATENCY = 0.5  # 실제 기상청 API 평균 응답시간 시뮬레이션 (초)


def mock_fetch_region(region_info: tuple) -> dict:
    """기상청 API 응답을 시뮬레이션하는 mock 함수"""
    level1, level2, nx, ny = region_info
    time.sleep(MOCK_LATENCY)  # API 응답 지연 시뮬레이션
    return {
        "LEVEL1": level1,
        "LEVEL2": level2,
        "PTY": 0, "REH": 60, "RN1": 0.0,
        "T1H": 18.5, "WSD": 3.2, "SKY": 1,
        "weather_condition": "Clear"
    }


def real_fetch_region(region_info: tuple) -> dict:
    """실제 기상청 API 호출"""
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo

    level1, level2, nx, ny = region_info
    now = datetime.now(ZoneInfo("Asia/Seoul"))
    if now.minute < 45:
        now -= timedelta(hours=1)
    base_date = now.strftime("%Y%m%d")
    base_time = now.strftime("%H") + "30"

    params = {
        "authKey": API_KEY,
        "numOfRows": 100,
        "pageNo": 1,
        "dataType": "JSON",
        "base_date": base_date,
        "base_time": base_time,
        "nx": nx,
        "ny": ny
    }
    url = BASE_URL + "?" + urlencode(params, safe="=")
    try:
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        return {"LEVEL1": level1, "LEVEL2": level2, "status": "ok"}
    except Exception as e:
        return {"LEVEL1": level1, "LEVEL2": level2, "status": f"error: {e}"}


fetch_region = real_fetch_region if USE_REAL_API else mock_fetch_region


# ──────────────────────────────────────────
# BEFORE: 직렬 처리 (현재 코드 방식)
# ──────────────────────────────────────────
def fetch_serial(regions: list) -> list:
    results = []
    for region in regions:
        result = fetch_region(region)
        results.append(result)
    return results


# ──────────────────────────────────────────
# AFTER: 병렬 처리 (개선 코드 방식)
# ──────────────────────────────────────────
def fetch_parallel(regions: list, max_workers: int = 10) -> list:
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(fetch_region, r): r for r in regions}
        for future in concurrent.futures.as_completed(futures):
            try:
                results.append(future.result())
            except Exception as e:
                results.append({"status": f"error: {e}"})
    return results


def run_benchmark(n_regions: int = 20, n_repeat: int = 3):
    regions = SAMPLE_REGIONS[:n_regions]
    mode = "실제 API" if USE_REAL_API else f"mock (지연 {MOCK_LATENCY}s/지역)"

    print(f"\n{'='*55}")
    print(f"  bench_weather_etl: 직렬 vs 병렬 날씨 API 벤치마크")
    print(f"  지역 수: {n_regions}개  |  반복: {n_repeat}회  |  모드: {mode}")
    print(f"{'='*55}")

    # ── BEFORE (직렬) ──
    serial_times = []
    print("\n[BEFORE] 직렬 처리 측정 중...")
    for i in range(n_repeat):
        start = time.perf_counter()
        fetch_serial(regions)
        elapsed = time.perf_counter() - start
        serial_times.append(elapsed)
        print(f"  Round {i+1}: {elapsed:.2f}s")

    serial_avg = statistics.mean(serial_times)

    # ── AFTER (병렬) ──
    parallel_times = []
    print("\n[AFTER]  병렬 처리 측정 중...")
    for i in range(n_repeat):
        start = time.perf_counter()
        fetch_parallel(regions)
        elapsed = time.perf_counter() - start
        parallel_times.append(elapsed)
        print(f"  Round {i+1}: {elapsed:.2f}s")

    parallel_avg = statistics.mean(parallel_times)
    improvement = (1 - parallel_avg / serial_avg) * 100

    print(f"\n{'='*55}")
    print(f"  결과 요약")
    print(f"{'='*55}")
    print(f"  [BEFORE] 직렬   평균: {serial_avg:.2f}s")
    print(f"  [AFTER]  병렬   평균: {parallel_avg:.2f}s")
    print(f"  개선율: {improvement:.1f}% 단축")
    print(f"{'='*55}")
    print(f"\n  이력서 수치 예시:")
    print(f"  기상청 API {n_regions}개 지역 순차 수집에서 ")
    print(f"  ThreadPoolExecutor 병렬 처리로 전환,")
    print(f"  fetch 단계 소요시간 {serial_avg:.0f}s → {parallel_avg:.1f}s ({improvement:.0f}% 단축)")


if __name__ == "__main__":
    run_benchmark(n_regions=20, n_repeat=3)
