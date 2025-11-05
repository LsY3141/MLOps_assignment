"""
캠퍼스메이트 백엔드 메인 애플리케이션
FastAPI 기반 REST API 서버
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import chat, admin
from app.utils.config import settings

# FastAPI 앱 초기화
app = FastAPI(
    title="CampusMate API",
    description="대학 행정 AI 챗봇 서비스 API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS 미들웨어 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(chat.router, prefix="/api/chat", tags=["Chat"])
app.include_router(admin.router, prefix="/api/admin", tags=["Admin"])


@app.get("/")
async def root():
    """
    헬스 체크 엔드포인트
    """
    return {
        "service": "CampusMate API",
        "status": "healthy",
        "version": "1.0.0"
    }


@app.get("/health")
async def health_check():
    """
    상세 헬스 체크
    """
    return {
        "status": "ok",
        "database": "connected",  # TODO: 실제 DB 연결 체크
        "aws_bedrock": "available"  # TODO: 실제 Bedrock 연결 체크
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
