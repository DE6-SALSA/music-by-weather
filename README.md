# Weatherify — 날씨 기반 음악 추천 시스템

현재 날씨를 기반으로 어울리는 음악을 추천하는 데이터 파이프라인 + API + 웹 대시보드 프로젝트입니다.

---

## 주요 기능

- **기상청 초단기예보 API**로 전국 ~250개 지역 날씨 수집 (매시간 자동 실행)
- **Last.fm API**로 글로벌 인기 트랙 및 태그 수집 (50분 주기 자동 실행)
- S3 업로드 → Redshift COPY 파이프라인 (Apache Airflow DAG)
- 날씨 조건(맑음/흐림/비/눈/바람 등)에 매핑된 음악 추천 (FastAPI)
- 지역별 날씨 실시간 조회 및 차트 순위 제공 (FastAPI)
- Streamlit 웹 대시보드 (Weatherify) — 날씨 애니메이션, 차트 순위, 태그 검색
- Airflow Task 실패 시 Slack 알림

---

## 시스템 아키텍처

```
[기상청 API]           [Last.fm API]
      │                      │
      ▼                      ▼
 weather_dag.py        track_dag.py        (Apache Airflow)
  ┌──────────┐        ┌────────────────┐
  │ fetch    │        │ extract_tracks │
  │ (병렬    │        │ enrich_with_   │  ← ThreadPoolExecutor 병렬화
  │  250지역)│        │ tags (병렬)    │
  └────┬─────┘        └──────┬─────────┘
       │ CSV                 │ Parquet
       ▼                     ▼
    [AWS S3]             [AWS S3]
       │                     │
       ▼ COPY                ▼ COPY (Staging 패턴)
  [Amazon Redshift]    [Amazon Redshift]
  raw_data.weather_data  raw_data.track_data
                         analytics_data.top_tag5

         │                    │
         └────────┬───────────┘
                  ▼
            [FastAPI 서버]          ← ThreadedConnectionPool
                  │
                  ▼
          [Streamlit 앱]
           (Weatherify)
```

---

## 기술 스택

| 분류 | 기술 |
|------|------|
| 파이프라인 오케스트레이션 | Apache Airflow 2.9.1 (CeleryExecutor) |
| 데이터 소스 | 기상청 API Hub (초단기예보), Last.fm API |
| 스토리지 | AWS S3 (CSV / Parquet), Amazon Redshift |
| API 서버 | FastAPI 0.116.1 + Uvicorn |
| 웹 대시보드 | Streamlit 1.46.1 |
| DB 클라이언트 | psycopg2 (ThreadedConnectionPool) |
| 직렬화 | pyarrow (Snappy Parquet) |
| 알림 | Slack Webhook |
| 인프라 | Docker Compose, GitHub Actions CI/CD |
| 언어 | Python 3.x |

---

## 데이터 파이프라인

### 1. 날씨 파이프라인 (`weather_pipeline` DAG)

스케줄: 매시간 40분 (`40 * * * *`)

```
fetch_weather_data → upload_to_s3 → copy_to_redshift
```

- `fetch_weather_data`: 기상청 초단기예보 API를 `ThreadPoolExecutor(max_workers=20)`로 병렬 호출 (~250개 지역, 직렬 ~125s → 병렬 ~8s)
- 날씨 조건 분류: `Clear / Cloudy / Rainy / Snowy / Stormy / Windy / Hot / Cold`
- S3에 CSV 업로드 후 Redshift `raw_data.weather_data`에 COPY

### 2. 음악 파이프라인 (`lastfm_to_s3_redshift_test_pipeline` DAG)

스케줄: 50분마다 (`*/50 * * * *`)

```
extract_tracks → enrich_with_tags → save_to_s3_parquet → copy_to_redshift
```

- `extract_tracks`: Last.fm `chart.getTopTracks`에서 3페이지씩 순차 수집 (페이지 로테이션)
- `enrich_with_tags`: `track.getInfo`로 태그 보강 — `ThreadPoolExecutor(max_workers=10)` 병렬 (직렬 ~75s → 병렬 ~8s)
- Snappy Parquet으로 S3 업로드
- `copy_to_redshift`: **Staging 테이블 패턴** 적용 — `raw_data.track_data_staging` → 트랜잭션 내 `track_data` 교체 → `analytics_data.top_tag5` UPDATE/INSERT → 실패 시 ROLLBACK

---

## Redshift 스키마

| 스키마 | 테이블 | 설명 |
|--------|--------|------|
| raw_data | weather_data | 기상청 날씨 원본 |
| raw_data | track_data | Last.fm 트랙 원본 |
| raw_data | track_data_staging | Staging (원자성 보장용) |
| raw_data | track_out | ETL 에러 레코드 |
| raw_data | bad_records_top_tag5 | 유효성 검사 실패 레코드 |
| analytics_data | top_tag5 | 태그 포함 최종 트랙 테이블 |
| analytics_data | weather_music | 날씨-음악 매핑 분석 테이블 |

---

## FastAPI 엔드포인트

| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/weather/current` | 특정 지역(level1, level2) 현재 날씨 조회 |
| GET | `/recommend/weather` | 현재 날씨 기반 음악 추천 |
| GET | `/search/music` | 곡명/아티스트/태그 키워드 검색 |
| GET | `/chart_rank` | 인기 차트 순위 (Last.fm 이미지 포함) |
| GET | `/chart/lyrics_simple` | 지역별 날씨-가사 유사도 기반 차트 |
| GET | `/locations/level1` | 시/도 목록 조회 |
| GET | `/locations/level2` | 시/군/구 목록 조회 |

> API 서버는 `psycopg2.ThreadedConnectionPool(minconn=2, maxconn=10)`으로 커넥션을 재사용합니다 (요청당 connect 오버헤드 ~200ms → ~5ms).

---

## 실행 방법

### 사전 요구사항

- Docker & Docker Compose
- AWS 자격증명 (S3, Redshift)
- 기상청 API Hub 키
- Last.fm API 키
- Slack Webhook URL (선택)

### Airflow 실행

```bash
docker compose -f docker-compose_git.yml up -d
```

Airflow 웹서버 기동 후 Variables 등록:

| Variable 키 | 설명 |
|-------------|------|
| `WEATHER_API_KEY` | 기상청 API Hub 인증키 |
| `S3_BUCKET_NAME` | S3 버킷명 |
| `S3_ACCESS_KEY` | AWS Access Key |
| `S3_SECRET_KEY` | AWS Secret Key |
| `LASTFM_API_KEY` | Last.fm API 키 |
| `SLACK_KEY` | Slack Webhook URL |

### FastAPI 서버 실행

```bash
cd api
pip install -r ../requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

환경변수로 Redshift 접속 정보를 설정해야 합니다 (`api/constants.py` 참고).

### Streamlit 앱 실행

```bash
cd app
streamlit run main_page.py
```

---

## CI/CD

| 워크플로우 | 트리거 | 역할 |
|-----------|--------|------|
| `dag_etl_ci.yml` | `dags/`, `etl/` 변경 → master push | Docker로 Airflow 기동, DAG import 에러 검사 |
| `dag_etl_cd.yml` | CI 성공 후 자동 트리거 | EC2에 DAG/ETL 코드 배포 |
| `api_cd.yml` | API 코드 변경 → master push | FastAPI 서버 배포 |
| `app_cd.yml` | App 코드 변경 → master push | Streamlit 앱 배포 |

---

## 프로젝트 구조

```
.
├── dags/
│   ├── weather_dag.py          # 기상청 파이프라인 DAG
│   └── track_dag.py            # Last.fm 파이프라인 DAG
├── etl/
│   ├── weather_etl.py          # 기상청 ETL 함수
│   ├── track_etl.py            # Last.fm ETL 함수 (병렬화 + Staging 패턴)
│   └── slack_alert.py          # Airflow 실패 알림
├── api/
│   ├── main.py                 # FastAPI 앱 진입점
│   ├── routers.py              # 엔드포인트 정의
│   ├── services.py             # 비즈니스 로직
│   ├── db.py                   # ThreadedConnectionPool 관리
│   └── constants.py            # Redshift 설정
├── app/
│   ├── main_page.py            # Streamlit 메인 페이지 (Weatherify)
│   └── pages/
│       ├── chart_rank.py       # 차트 순위 페이지
│       └── lyrics_page.py      # 가사 페이지
├── benchmark/                  # 성능 벤치마크 스크립트
├── docs/                       # ADR 문서 (ADR-000 ~ ADR-007)
├── docker-compose_git.yml      # Airflow + PostgreSQL + Redis
└── requirements.txt
```
