"""
데이터베이스 연결 및 세션 관리
- SQLAlchemy 엔진 생성
- 데이터베이스 세션 생성 및 관리
- FastAPI 의존성 주입을 위한 get_db 함수 제공
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.utils.config import Settings

# 1. 설정 파일에서 데이터베이스 URL 로드
settings = Settings()
DATABASE_URL = str(settings.DATABASE_URL)

if not DATABASE_URL:
    raise ValueError("DATABASE_URL이 .env 파일에 설정되지 않았습니다.")

# 2. SQLAlchemy 엔진 생성
engine = create_engine(DATABASE_URL)

# 3. 데이터베이스 세션 생성을 위한 SessionLocal 클래스 생성
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """
    각 API 요청에 대한 데이터베이스 세션을 생성하고,
    요청이 완료되면 세션을 닫는 FastAPI 의존성 함수.
    
    Yields:
        Session: SQLAlchemy 데이터베이스 세션 객체
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
