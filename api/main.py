from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .db import test_redshift_connection
from .routers import router

app = FastAPI(
    title="Music & Weather Recommendation API",
    description="날씨 정보와 사용자 태그를 기반으로 음악을 추천하는 API",
    version="0.1.0",
)

origins = [
    "http://localhost",
    "http://localhost:8501",
    "http://127.0.0.1:8501",
    "http://15.165.108.160:8501",
    "http://10.0.45.211:8000"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    test_redshift_connection()

app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
