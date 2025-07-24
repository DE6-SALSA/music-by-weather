# 1. Python 3.10 베이스 이미지 사용
FROM python:3.10-slim

# 2. 환경변수 설정 (Python 버퍼링 비활성화 등)
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 3. 작업 디렉토리 생성
WORKDIR /api

# 4. 종속성 복사 및 설치
COPY ./requirements.txt /api/requirements.txt
RUN pip install --upgrade pip && \
    pip install -r requirements.txt && \
    rm -rf /root/.cache/pip

# 5. 소스 코드 복사
COPY ./api .

# 6. FastAPI 실행
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
