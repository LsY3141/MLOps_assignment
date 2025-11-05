"""
데이터베이스 모델 정의
SQLAlchemy + pgvector
"""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.dialects.postgresql import ARRAY
from datetime import datetime
from pgvector.sqlalchemy import Vector

Base = declarative_base()


class School(Base):
    """
    학교 정보 테이블
    """
    __tablename__ = "schools"
    
    id = Column(String(50), primary_key=True)
    name = Column(String(200), nullable=False)
    domain = Column(String(100), unique=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Document(Base):
    """
    문서 메타데이터 테이블
    """
    __tablename__ = "documents"
    
    id = Column(String(50), primary_key=True)
    school_id = Column(String(50), ForeignKey("schools.id"), nullable=False, index=True)
    title = Column(String(500), nullable=False)
    category = Column(String(50), nullable=False, index=True)
    department = Column(String(100), nullable=False)
    contact = Column(String(100))
    source_type = Column(String(20), nullable=False)  # 'upload' or 'rss'
    source_url = Column(String(500))  # RSS 링크 또는 S3 키
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DocumentChunk(Base):
    """
    문서 청크 및 벡터 임베딩 테이블
    """
    __tablename__ = "document_chunks"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(String(50), ForeignKey("documents.id"), nullable=False, index=True)
    school_id = Column(String(50), ForeignKey("schools.id"), nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    
    # pgvector 타입 (1536차원 - Titan Embeddings)
    embedding = Column(Vector(1536), nullable=False)
    
    created_at = Column(DateTime, default=datetime.utcnow)


class DefaultContact(Base):
    """
    카테고리별 기본 담당 부서 테이블
    """
    __tablename__ = "default_contacts"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    school_id = Column(String(50), ForeignKey("schools.id"), nullable=False, index=True)
    category = Column(String(50), nullable=False, index=True)
    department = Column(String(100), nullable=False)
    contact_person = Column(String(100))
    phone = Column(String(50))
    email = Column(String(100))
    location = Column(String(200))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class RSSFeed(Base):
    """
    RSS 피드 정보 테이블
    """
    __tablename__ = "rss_feeds"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    school_id = Column(String(50), ForeignKey("schools.id"), nullable=False, index=True)
    feed_url = Column(String(500), nullable=False)
    category = Column(String(50), nullable=False)
    department = Column(String(100), nullable=False)
    contact = Column(String(100))
    is_active = Column(Integer, default=1)  # 1: 활성, 0: 비활성
    last_crawled_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ChatSession(Base):
    """
    채팅 세션 테이블
    """
    __tablename__ = "chat_sessions"
    
    id = Column(String(50), primary_key=True)
    school_id = Column(String(50), ForeignKey("schools.id"), nullable=False, index=True)
    user_id = Column(String(50))  # 선택적 사용자 식별자
    created_at = Column(DateTime, default=datetime.utcnow)
    last_activity_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ChatMessage(Base):
    """
    채팅 메시지 로그 테이블
    """
    __tablename__ = "chat_messages"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(50), ForeignKey("chat_sessions.id"), nullable=False, index=True)
    school_id = Column(String(50), ForeignKey("schools.id"), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # 'user' or 'assistant'
    content = Column(Text, nullable=False)
    response_type = Column(String(20))  # 'rag' or 'fallback'
    source_documents = Column(ARRAY(String))  # 참조 문서 ID 배열
    rating = Column(Integer)  # 사용자 피드백 (1-5)
    feedback_comment = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
