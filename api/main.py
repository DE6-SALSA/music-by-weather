# main.py 파일 내용 (수정될 부분만 예시)

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
import sys

# 프로젝트 루트 디렉토리를 PYTHONPATH에 추가 (임포트 문제 해결을 위해)
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))


# test_redshift_connection 임포트 (이전 단계에서 수정)
from api.db import test_redshift_connection

# 기존 코드에서 다음 라인들을 찾아서 수정:
# from api.routers import locations, tags, musics
# 이 라인을 다음과 같이 변경합니다.
from api.routers import router as api_router # api.routers.py 파일에서 router 객체를 임포트합니다.

from api.constants import FASTAPI_BASE_URL, FRONTEND_URL, IS_PROD, DOCS_URL

app = FastAPI(docs_url=DOCS_URL)

# CORS 설정 (기존과 동일)
origins = [
    FRONTEND_URL,
    "http://localhost:3000",
    "http://localhost:8501",
    "http://127.0.0.1:8501",
    "http://15.165.108.160:8501", # 당신의 Streamlit 프론트엔드 주소
    "http://10.0.45.211:8000" # 당신의 FastAPI 백엔드 주소 (개발용)
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 기존의 app.include_router 라인들을 모두 제거하고 아래와 같이 하나로 합칩니다.
app.include_router(api_router) # api_router에 모든 엔드포인트가 포함되어 있습니다.

@app.get("/")
def read_root():
    return {"message": "Welcome to the Music by Weather API!"}

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.get("/db-test")
def db_test_endpoint():
    """
    데이터베이스 연결을 테스트하는 엔드포인트.
    """
    try:
        test_redshift_connection()
        return {"status": "Database connection successful!"}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database test failed: {e}")

# If you need to run the app directly (e.g., for local development without uvicorn command)
# if __name__ == "__main__":
#    uvicorn.run(app, host="0.0.0.0", port=8000)