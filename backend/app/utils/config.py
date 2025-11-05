"""
환경 변수 및 설정 관리
"""

from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """
    애플리케이션 설정
    """
    # 기본 설정
    APP_NAME: str = "CampusMate"
    DEBUG: bool = True
    
    # AWS 설정
    AWS_REGION: str = "ap-northeast-2"
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    
    # Bedrock 모델 설정
    BEDROCK_CLAUDE_MODEL: str = "anthropic.claude-3-5-sonnet-20241022-v2:0"
    BEDROCK_EMBEDDING_MODEL: str = "amazon.titan-embed-text-v1"
    
    # 데이터베이스 설정
    DATABASE_URL: str = "postgresql://user:password@localhost:5432/campusmate"
    
    # S3 설정
    S3_BUCKET_NAME: str = "campusmate-documents"
    
    # CORS 설정
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:3001",
    ]
    
    # RAG 설정
    VECTOR_SEARCH_TOP_K: int = 3
    SIMILARITY_THRESHOLD: float = 0.75
    CHUNK_SIZE: int = 500
    CHUNK_OVERLAP: int = 50
    
    # RSS 크롤링 설정
    RSS_CRAWL_SCHEDULE: str = "cron(0 6 * * ? *)"  # 매일 오전 6시
    
    class Config:
        env_file = ".env"
        case_sensitive = True


# 설정 인스턴스 생성
settings = Settings()
