from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .db import test_postgres_connection  # Changed from test_redshift_connection
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
    "http://10.0.45.211:8501",  # Added for Streamlit frontend on private IP
    "http://10.0.45.211",       # Added for EC2 private IP
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
    test_postgres_connection()  # Changed to PostgreSQL test

app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)  # Changed to 0.0.0.0 for EC2 access
    # For production, use: gunicorn -w 4 -k uvicorn.workers.UvicornWorker main:app --bind 0.0.0.0:8000
    # Note: If folder structure changed (e.g., moved to src/), use src.main:app for gunicorn