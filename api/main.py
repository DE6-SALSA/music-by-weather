from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import router
from db import test_redshift_connection


app = FastAPI(
    title="Music & Weather Recommendation API",
    description="날씨 정보와 사용자 태그를 기반으로 음악을 추천하는 API",
    version="0.1.0",
)

# --- CORS 설정 ---
origins = [
    "http://localhost",
    "http://localhost:8501",
    "http://127.0.0.1:8501",
<<<<<<< Updated upstream
    "http://15.165.108.160:8501"
=======
    "http://15.165.108.160:8501", # 도메인이 있다면 추가 
>>>>>>> Stashed changes
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

@app.on_event("startup")
async def startup_event():
    test_redshift_connection()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
