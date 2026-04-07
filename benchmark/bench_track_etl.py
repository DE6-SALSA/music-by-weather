"""
bench_track_etl.py
==================
enrich_with_tags: 직렬(Before) vs 병렬(After) Last.fm API 호출 성능 비교

사용법:
    export LASTFM_API_KEY=your_api_key
    python benchmark/bench_track_etl.py

출력:
    직렬 소요시간, 병렬 소요시간, 개선율(%)
"""

import os
import time
import requests
import concurrent.futures
import statistics

API_KEY = os.environ.get("LASTFM_API_KEY", "")
BASE_URL = "http://ws.audioscrobbler.com/2.0/"

# 실제 Last.fm 차트 상위 트랙 샘플 (고정값으로 재현성 보장)
SAMPLE_TRACKS = [
    ("The Beatles", "Come Together"),
    ("Led Zeppelin", "Stairway to Heaven"),
    ("Queen", "Bohemian Rhapsody"),
    ("Pink Floyd", "Comfortably Numb"),
    ("Radiohead", "Creep"),
    ("Nirvana", "Smells Like Teen Spirit"),
    ("David Bowie", "Heroes"),
    ("The Rolling Stones", "Paint It Black"),
    ("Metallica", "Nothing Else Matters"),
    ("AC/DC", "Highway to Hell"),
    ("Fleetwood Mac", "Go Your Own Way"),
    ("Eagles", "Hotel California"),
    ("Bruce Springsteen", "Born to Run"),
    ("U2", "With or Without You"),
    ("R.E.M.", "Losing My Religion"),
    ("Pearl Jam", "Black"),
    ("Soundgarden", "Black Hole Sun"),
    ("Alice in Chains", "Rooster"),
    ("Red Hot Chili Peppers", "Under the Bridge"),
    ("Foo Fighters", "Everlong"),
]


def fetch_single_track(artist: str, title: str) -> tuple:
    """단일 트랙 정보 조회 (실제 API 호출)"""
    params = {
        "method": "track.getInfo",
        "artist": artist,
        "track": title,
        "api_key": API_KEY,
        "format": "json"
    }
    try:
        resp = requests.get(BASE_URL, params=params, timeout=10)
        info = resp.json().get("track", {})
        tags = [t["name"] for t in info.get("toptags", {}).get("tag", [])][:5]
        tags += [None] * (5 - len(tags))
        playcount = int(info.get("playcount", 0))
        listeners = int(info.get("listeners", 0))
        return (artist, title, playcount, listeners, *tags)
    except Exception:
        return (artist, title, 0, 0, None, None, None, None, None)


# ──────────────────────────────────────────
# BEFORE: 직렬 처리 (현재 코드 방식)
# ──────────────────────────────────────────
def enrich_serial(tracks: list) -> tuple:
    results = []
    for artist, title in tracks:
        result = fetch_single_track(artist, title)
        results.append(result)
        time.sleep(0.2)  # 현재 코드와 동일한 rate limit 대기
    return results


# ──────────────────────────────────────────
# AFTER: 병렬 처리 (개선 코드 방식)
# ──────────────────────────────────────────
def enrich_parallel(tracks: list, max_workers: int = 10) -> list:
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(fetch_single_track, artist, title): (artist, title)
            for artist, title in tracks
        }
        for future in concurrent.futures.as_completed(futures):
            try:
                results.append(future.result())
            except Exception as e:
                artist, title = futures[future]
                results.append((artist, title, 0, 0, None, None, None, None, None))
    return results


def run_benchmark(n_tracks: int = 20, n_repeat: int = 3):
    if not API_KEY:
        print("❌ LASTFM_API_KEY 환경변수가 설정되지 않았습니다.")
        print("   export LASTFM_API_KEY=your_api_key")
        return

    tracks = SAMPLE_TRACKS[:n_tracks]
    print(f"\n{'='*55}")
    print(f"  bench_track_etl: 직렬 vs 병렬 API 호출 벤치마크")
    print(f"  트랙 수: {n_tracks}개  |  반복: {n_repeat}회")
    print(f"{'='*55}")

    # ── BEFORE (직렬) ──
    serial_times = []
    print("\n[BEFORE] 직렬 처리 측정 중...")
    for i in range(n_repeat):
        start = time.perf_counter()
        enrich_serial(tracks)
        elapsed = time.perf_counter() - start
        serial_times.append(elapsed)
        print(f"  Round {i+1}: {elapsed:.2f}s")

    serial_avg = statistics.mean(serial_times)
    serial_min = min(serial_times)

    # ── AFTER (병렬) ──
    parallel_times = []
    print("\n[AFTER]  병렬 처리 측정 중...")
    for i in range(n_repeat):
        start = time.perf_counter()
        enrich_parallel(tracks)
        elapsed = time.perf_counter() - start
        parallel_times.append(elapsed)
        print(f"  Round {i+1}: {elapsed:.2f}s")

    parallel_avg = statistics.mean(parallel_times)
    parallel_min = min(parallel_times)

    improvement = (1 - parallel_avg / serial_avg) * 100

    print(f"\n{'='*55}")
    print(f"  결과 요약")
    print(f"{'='*55}")
    print(f"  [BEFORE] 직렬   평균: {serial_avg:.2f}s  최솟값: {serial_min:.2f}s")
    print(f"  [AFTER]  병렬   평균: {parallel_avg:.2f}s  최솟값: {parallel_min:.2f}s")
    print(f"  개선율: {improvement:.1f}% 단축")
    print(f"{'='*55}")
    print(f"\n  이력서 수치 예시:")
    print(f"  Last.fm API {n_tracks}개 트랙 직렬 호출 방식에서 ")
    print(f"  ThreadPoolExecutor 병렬 처리로 전환,")
    print(f"  enrich 단계 소요시간 {serial_avg:.0f}s → {parallel_avg:.0f}s ({improvement:.0f}% 단축)")


if __name__ == "__main__":
    run_benchmark(n_tracks=20, n_repeat=3)
