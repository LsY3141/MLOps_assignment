import boto3
import streamlit as st
from langchain_aws import ChatBedrock
# BedrockEmbeddings import 수정
try:
    from langchain_aws import BedrockEmbeddings
except ImportError:
    try:
        from langchain_community.embeddings import BedrockEmbeddings
    except ImportError:
        # BedrockEmbeddings를 사용할 수 없는 경우 None으로 설정
        BedrockEmbeddings = None
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import CharacterTextSplitter
from langchain_community.vectorstores import PGVector
import feedparser
import tempfile
import os
import pandas as pd
import numpy as np
from datetime import datetime
import psycopg2
from sqlalchemy import create_engine, text
import json
from typing import List, Dict
import re

# 페이지 설정
st.set_page_config(
    page_title="학사 정보 검색 시스템",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# AWS 및 DB 설정 (하드코딩)
AWS_REGION = "us-west-1"
S3_BUCKET_NAME = "ysu-ml-a-13-s3"
DATABASE_URL = "postgresql://postgres:12345678aA@a-13-rds.cpyomug2w3oq.us-west-1.rds.amazonaws.com:5432/postgres"
DB_HOST = "a-13-rds.cpyomug2w3oq.us-west-1.rds.amazonaws.com"
DB_PORT = 5432
DB_NAME = "postgres"
DB_USER = "postgres"
DB_PASSWORD = "12345678aA"

# 메인 타이틀
st.title("🔍 학사 정보 검색 시스템")
st.caption("RAG(Retrieval-Augmented Generation) 기반 문서 검색 및 일반 AI 챗봇")

# 학교 선택 UI (전체 앱에 적용)
def render_school_selector(engine):
    """학교 선택 UI를 렌더링합니다."""
    schools = get_schools_list(engine)
    
    # 세션 상태에 선택된 학교 저장
    if 'selected_school' not in st.session_state:
        st.session_state.selected_school = list(schools.keys())[0]
    
    # 학교 선택 드롭다운
    selected_school = st.selectbox(
        "🏫 학교 선택",
        options=list(schools.keys()),
        index=list(schools.keys()).index(st.session_state.selected_school),
        key="school_selector"
    )
    
    # 선택이 변경되면 세션 상태 업데이트
    if selected_school != st.session_state.selected_school:
        st.session_state.selected_school = selected_school
        # RSS URL 입력 필드 초기화
        st.session_state.rss_url_input = ""
        st.rerun()
    
    school_id = schools[selected_school]
    
    # 선택된 학교 정보 표시
    st.info(f"📚 현재 선택: **{selected_school}** (ID: {school_id})")
    
    return school_id, selected_school

# AWS 클라이언트 초기화 (EC2 IAM 역할 사용)
@st.cache_resource
def init_aws_clients():
    """EC2 IAM 역할을 사용하여 AWS 클라이언트들을 초기화합니다."""
    try:
        # bedrock-runtime 클라이언트로 변경
        bedrock_client = boto3.client("bedrock-runtime", region_name=AWS_REGION)
        s3_client = boto3.client("s3", region_name=AWS_REGION)
        
        # 임베딩 초기화 (오류 처리 강화)
        embeddings = None
        if BedrockEmbeddings is not None:
            try:
                embeddings = BedrockEmbeddings(
                    client=boto3.client("bedrock-runtime", region_name=AWS_REGION),
                    region_name=AWS_REGION,
                    model_id="cohere.embed-v4:0"
                )
            except Exception as e:
                st.warning(f"임베딩 모델 초기화 실패: {str(e)}")
        else:
            st.warning("BedrockEmbeddings를 사용할 수 없습니다. 텍스트 검색만 사용됩니다.")
        
        return bedrock_client, embeddings, s3_client
    except Exception as e:
        st.error(f"AWS 클라이언트 초기화 실패: {str(e)}")
        return None, None, None

# PostgreSQL 연결 및 벡터 스토어 초기화
@st.cache_resource
def init_postgresql_vectorstore():
    """PostgreSQL을 벡터 스토어로 초기화합니다."""
    try:
        engine = create_engine(DATABASE_URL)
        
        # 연결 테스트 및 필요한 컬럼 추가
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            
            # documents 테이블에 필요한 컬럼들 추가 (없으면)
            try:
                conn.execute(text("ALTER TABLE documents ADD COLUMN IF NOT EXISTS processed BOOLEAN DEFAULT FALSE"))
                conn.execute(text("ALTER TABLE documents ADD COLUMN IF NOT EXISTS chunks_count INTEGER DEFAULT 0"))
                conn.commit()
            except Exception as e:
                # 컬럼이 이미 있거나 권한 문제면 무시
                pass
        
        return engine
    except Exception as e:
        st.error(f"PostgreSQL 초기화 실패: {str(e)}")
        return None

# PGVector 벡터 스토어 초기화
@st.cache_resource 
def init_pgvector(_embeddings, _engine):
    """PGVector 벡터 스토어를 초기화합니다."""
    if not _embeddings:
        st.warning("임베딩 모델이 없어 벡터 검색을 사용할 수 없습니다.")
        return None
    
    try:
        vectorstore = PGVector(
            connection_string=DATABASE_URL,
            embedding_function=_embeddings,
            collection_name="university_docs"
        )
        return vectorstore
    except Exception as e:
        st.error(f"PGVector 초기화 실패: {str(e)}")
        st.warning("벡터 검색 대신 텍스트 검색을 사용합니다.")
        return None

def get_schools_list(engine):
    """학교 목록을 조회합니다."""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT id, name, code FROM schools ORDER BY name"))
            schools = result.fetchall()
            return {school[1]: school[0] for school in schools}  # {name: id} 형태
    except Exception as e:
        st.error(f"학교 목록 조회 실패: {str(e)}")
        return {"연성대학교": 1, "연세대학교": 2}  # 기본값

def get_school_stats(engine, school_id):
    """선택한 학교의 통계를 조회합니다."""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT 
                    COUNT(d.id) as total_documents,
                    SUM(CASE WHEN d.processed = true THEN 1 ELSE 0 END) as processed_documents,
                    SUM(COALESCE(d.chunks_count, 0)) as total_chunks
                FROM documents d
                WHERE d.school_id = :school_id
            """), {"school_id": school_id})
            stats = result.fetchone()
            return {
                "total_documents": stats[0] or 0,
                "processed_documents": stats[1] or 0,
                "total_chunks": stats[2] or 0
            }
    except Exception as e:
        st.error(f"통계 조회 실패: {str(e)}")
        return {"total_documents": 0, "processed_documents": 0, "total_chunks": 0}

def upload_to_s3(file, s3_client, bucket_name, key):
    """파일을 S3에 업로드합니다."""
    try:
        s3_client.upload_fileobj(file, bucket_name, key)
        return True
    except Exception as e:
        st.error(f"S3 업로드 실패: {str(e)}")
        return False

def process_pdf_from_s3(s3_client, bucket_name, key, vectorstore, embeddings, engine):
    """S3의 PDF 파일을 처리하여 PostgreSQL DB에 저장합니다."""
    try:
        # 임시 파일로 다운로드
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            s3_client.download_fileobj(bucket_name, key, tmp_file)
            tmp_path = tmp_file.name
        
        # PDF 로드 및 청크 분할
        pdf_loader = PyPDFLoader(tmp_path)
        splitter = CharacterTextSplitter.from_tiktoken_encoder(
            separator="\n",
            chunk_size=800,
            chunk_overlap=100,
        )
        documents = pdf_loader.load_and_split(text_splitter=splitter)
        
        # 문서 메타데이터를 DB에 저장
        chunks_processed = 0
        document_id = None
        
        with engine.connect() as conn:
            # 1. 기존 문서가 있는지 확인 (source_url 기준)
            source_url = f"s3://{bucket_name}/{key}"
            existing_doc = conn.execute(text("""
                SELECT id FROM documents 
                WHERE source_url = :source_url OR file_name = :file_name
            """), {
                "source_url": source_url,
                "file_name": key.split('/')[-1]
            }).fetchone()
            
            if existing_doc:
                # 기존 문서 업데이트
                document_id = existing_doc[0]
                conn.execute(text("""
                    UPDATE documents 
                    SET processed = TRUE, chunks_count = :chunks_count
                    WHERE id = :document_id
                """), {
                    "document_id": document_id,
                    "chunks_count": len(documents)
                })
            else:
                # 새 문서 생성
                result = conn.execute(text("""
                    INSERT INTO documents (school_id, file_name, source_url, category, processed, chunks_count)
                    VALUES (1, :file_name, :source_url, 'pdf', TRUE, :chunks_count)
                    RETURNING id
                """), {
                    "file_name": key.split('/')[-1],
                    "source_url": source_url,
                    "chunks_count": len(documents)
                })
                document_id = result.fetchone()[0]
            
            # 2. 기존 청크 삭제 (재처리인 경우)
            conn.execute(text("DELETE FROM document_chunks WHERE document_id = :document_id"), 
                         {"document_id": document_id})
            
            # 3. 새로운 청크들 저장
            for i, doc in enumerate(documents):
                try:
                    # 임베딩이 있으면 벡터와 함께 저장
                    embedding_vector = [0.0] * 1536  # 기본값
                    if embeddings:
                        try:
                            embedding_vector = embeddings.embed_query(doc.page_content)
                        except Exception as e:
                            st.warning(f"임베딩 생성 실패: {str(e)}")
                    
                    conn.execute(text("""
                        INSERT INTO document_chunks (document_id, chunk_text, embedding)
                        VALUES (:document_id, :chunk_text, :embedding)
                    """), {
                        "document_id": document_id,
                        "chunk_text": doc.page_content,
                        "embedding": embedding_vector
                    })
                    chunks_processed += 1
                except Exception as e:
                    st.warning(f"청크 저장 실패: {str(e)}")
                    continue
            
            conn.commit()
        
        # 임시 파일 삭제
        os.unlink(tmp_path)
        
        return chunks_processed
    except Exception as e:
        st.error(f"PDF 처리 실패: {str(e)}")
        return 0

def process_rss_feed(rss_url, vectorstore, engine, embeddings=None):
    """RSS 피드를 중복 방지하며 DB에 저장합니다."""
    try:
        feed = feedparser.parse(rss_url)
        chunks_processed = 0
        skipped_duplicates = 0
        
        with engine.connect() as conn:
            # 1. 기존 RSS 문서가 있는지 확인
            existing_doc = conn.execute(text("""
                SELECT id FROM documents 
                WHERE source_url = :source_url AND category = 'rss'
            """), {"source_url": rss_url}).fetchone()
            
            if existing_doc:
                document_id = existing_doc[0]
            else:
                # 새 RSS 문서 생성
                result = conn.execute(text("""
                    INSERT INTO documents (school_id, source_url, category, processed, chunks_count)
                    VALUES (1, :source_url, 'rss', FALSE, 0)
                    RETURNING id
                """), {"source_url": rss_url})
                document_id = result.fetchone()[0]
            
            # 2. 기존 청크들의 제목과 링크 조회 (중복 확인용)
            existing_contents = conn.execute(text("""
                SELECT chunk_text FROM document_chunks 
                WHERE document_id = :document_id
            """), {"document_id": document_id}).fetchall()
            
            # 기존 제목들 추출 (중복 확인용)
            existing_titles = set()
            existing_links = set()
            for content_row in existing_contents:
                content = content_row[0]
                # 제목과 링크 추출
                for line in content.split('\n'):
                    if line.strip().startswith('제목:'):
                        title = line.replace('제목:', '').strip()
                        existing_titles.add(title)
                    elif line.strip().startswith('링크:'):
                        link = line.replace('링크:', '').strip()
                        existing_links.add(link)
            
            # 3. RSS 항목들 처리 (중복 확인)
            for entry in feed.entries:
                entry_title = entry.get('title', '').strip()
                entry_link = entry.get('link', '').strip()
                
                # 중복 확인: 제목 또는 링크가 이미 존재하면 스킵
                if entry_title in existing_titles or entry_link in existing_links:
                    skipped_duplicates += 1
                    continue
                
                # 새로운 항목 처리
                content = f"""
제목: {entry_title}
내용: {entry.get('summary', entry.get('description', ''))}
링크: {entry_link}
발행일: {entry.get('published', '')}
                """
                
                # 텍스트 분할
                splitter = CharacterTextSplitter.from_tiktoken_encoder(
                    separator="\n",
                    chunk_size=800,
                    chunk_overlap=100,
                )
                chunks = splitter.split_text(content)
                
                for chunk in chunks:
                    try:
                        # 임베딩이 있으면 벡터와 함께 저장
                        embedding_vector = [0.0] * 1536  # 기본값
                        if embeddings:
                            try:
                                embedding_vector = embeddings.embed_query(chunk)
                            except:
                                pass
                        
                        conn.execute(text("""
                            INSERT INTO document_chunks (document_id, chunk_text, embedding)
                            VALUES (:document_id, :chunk_text, :embedding)
                        """), {
                            "document_id": document_id,
                            "chunk_text": chunk,
                            "embedding": embedding_vector
                        })
                        chunks_processed += 1
                        
                        # 새로 추가된 제목과 링크를 기존 세트에 추가 (다음 항목 중복 확인용)
                        existing_titles.add(entry_title)
                        existing_links.add(entry_link)
                        
                    except Exception as e:
                        st.warning(f"청크 저장 실패: {str(e)}")
                        continue
            
            # 4. 처리 상태 업데이트 (총 청크 수 계산)
            total_chunks = conn.execute(text("""
                SELECT COUNT(*) FROM document_chunks WHERE document_id = :document_id
            """), {"document_id": document_id}).fetchone()[0]
            
            conn.execute(text("""
                UPDATE documents 
                SET processed = TRUE, chunks_count = :chunks_count
                WHERE id = :document_id
            """), {
                "document_id": document_id,
                "chunks_count": total_chunks
            })
            
            conn.commit()
        
        # RSS 피드 정보를 rss_feeds 테이블에도 저장 (기존 구조 유지)
        try:
            with engine.connect() as conn:
                conn.execute(text("""
                    INSERT INTO rss_feeds (school_id, url)
                    VALUES (1, :rss_url)
                    ON CONFLICT (url) DO NOTHING
                """), {"rss_url": rss_url})
                conn.commit()
        except:
            pass  # rss_feeds 테이블 오류는 무시
        
        # 결과 메시지에 중복 스킵 정보 포함
        if skipped_duplicates > 0:
            st.info(f"📊 처리 결과: 신규 {chunks_processed}개 청크 추가, 중복 {skipped_duplicates}개 항목 스킵")
        
        return chunks_processed
    except Exception as e:
        st.error(f"RSS 피드 처리 실패: {str(e)}")
        return 0

def get_school_code_by_id(engine, school_id):
    """school_id로 학교 코드를 조회합니다."""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT code FROM schools WHERE id = :school_id"), 
                                 {"school_id": school_id})
            school = result.fetchone()
            return school[0] if school else "UNK"
    except Exception as e:
        return "UNK"

def save_file_metadata(engine, filename, s3_key, doc_type, school_id=1):
    """파일 메타데이터를 documents 테이블에 저장합니다 (school_id 포함)."""
    try:
        with engine.connect() as conn:
            # source_url로 기존 문서 확인
            source_url = s3_key if s3_key.startswith('s3://') else f"s3://{S3_BUCKET_NAME}/{s3_key}"
            
            existing_doc = conn.execute(text("""
                SELECT id FROM documents 
                WHERE source_url = :source_url OR file_name = :filename
            """), {"source_url": source_url, "filename": filename}).fetchone()
            
            if not existing_doc:
                # 새 문서만 저장 (중복 방지) - school_id 포함
                conn.execute(text("""
                    INSERT INTO documents (school_id, file_name, source_url, category, processed, chunks_count)
                    VALUES (:school_id, :filename, :source_url, :doc_type, FALSE, 0)
                """), {
                    "school_id": school_id,
                    "filename": filename,
                    "source_url": source_url,
                    "doc_type": doc_type
                })
                conn.commit()
        return True
    except Exception as e:
        st.error(f"메타데이터 저장 실패: {str(e)}")
        return False

def get_file_metadata(engine, school_id=None):
    """documents 테이블에서 파일 메타데이터를 조회합니다 (학교별 필터링)."""
    try:
        if school_id:
            # 특정 학교의 파일만 조회
            df = pd.read_sql("""
                SELECT d.id, d.file_name as filename, 
                       d.source_url as s3_key, 
                       d.created_at as upload_date, 
                       d.category as document_type, 
                       COALESCE(d.processed, FALSE) as processed, 
                       COALESCE(d.chunks_count, 0) as chunks_count
                FROM documents d
                WHERE d.category != 'rss' AND d.school_id = %(school_id)s
                ORDER BY d.created_at DESC
            """, engine, params={"school_id": school_id})
        else:
            # 모든 학교의 파일 조회
            df = pd.read_sql("""
                SELECT id, file_name as filename, 
                       source_url as s3_key, 
                       created_at as upload_date, 
                       category as document_type, 
                       COALESCE(processed, FALSE) as processed, 
                       COALESCE(chunks_count, 0) as chunks_count
                FROM documents 
                WHERE category != 'rss'
                ORDER BY created_at DESC
            """, engine)
        return df
    except Exception as e:
        st.error(f"메타데이터 조회 실패: {str(e)}")
        return pd.DataFrame()

def get_rss_feeds(engine, school_id=None):
    """RSS 피드 목록을 조회합니다 (rss_feeds 테이블 기반)."""
    try:
        if school_id:
            # 특정 학교의 RSS만 조회
            df = pd.read_sql("""
                SELECT rf.id, rf.url as rss_url, rf.title, rf.last_processed,
                        rf.processed_count, rf.status, rf.created_at
                FROM rss_feeds rf
                WHERE rf.school_id = %(school_id)s
                ORDER BY rf.created_at DESC
            """, engine, params={"school_id": school_id})
        else:
            # 모든 학교의 RSS 조회
            df = pd.read_sql("""
                SELECT rf.id, rf.url as rss_url, rf.title, rf.last_processed,
                        rf.processed_count, rf.status, rf.created_at,
                        s.name as school_name
                FROM rss_feeds rf
                JOIN schools s ON rf.school_id = s.id
                ORDER BY rf.created_at DESC
            """, engine)
        return df
    except Exception as e:
        st.error(f"RSS 피드 조회 실패: {str(e)}")
        return pd.DataFrame()

def add_rss_feed(engine, school_id, rss_url):
    """새 RSS 피드를 rss_feeds 테이블에 추가합니다."""
    try:
        # RSS 피드 정보 가져오기
        feed = feedparser.parse(rss_url)
        feed_title = feed.feed.get('title', rss_url)
        
        with engine.connect() as conn:
            # 중복 확인 및 추가
            result = conn.execute(text("""
                INSERT INTO rss_feeds (school_id, url, title, status)
                VALUES (:school_id, :url, :title, 'active')
                ON CONFLICT (school_id, url) DO NOTHING
                RETURNING id
            """), {
                "school_id": school_id,
                "url": rss_url,
                "title": feed_title
            })
            
            new_feed = result.fetchone()
            conn.commit()
            
            if new_feed:
                return new_feed[0]  # 새로 생성된 ID
            else:
                # 이미 존재하는 경우 기존 ID 반환
                existing = conn.execute(text("""
                    SELECT id FROM rss_feeds 
                    WHERE school_id = :school_id AND url = :url
                """), {"school_id": school_id, "url": rss_url}).fetchone()
                return existing[0] if existing else None
                
    except Exception as e:
        st.error(f"RSS 피드 추가 실패: {str(e)}")
        return None

def delete_rss_feed(engine, rss_feed_id):
    """RSS 피드를 삭제합니다 (관련 documents와 chunks도 함께)."""
    try:
        with engine.connect() as conn:
            # RSS 피드 URL 조회
            rss_info = conn.execute(text("""
                SELECT url, school_id FROM rss_feeds WHERE id = :rss_id
            """), {"rss_id": rss_feed_id}).fetchone()
            
            if not rss_info:
                return False
            
            rss_url, school_id = rss_info
            
            # 관련 documents 찾기
            docs = conn.execute(text("""
                SELECT id FROM documents 
                WHERE source_url = :url AND category = 'rss' AND school_id = :school_id
            """), {"url": rss_url, "school_id": school_id}).fetchall()
            
            # documents와 연관된 chunks 삭제
            for doc in docs:
                conn.execute(text("""
                    DELETE FROM document_chunks WHERE document_id = :doc_id
                """), {"doc_id": doc[0]})
            
            # documents 삭제
            conn.execute(text("""
                DELETE FROM documents 
                WHERE source_url = :url AND category = 'rss' AND school_id = :school_id
            """), {"url": rss_url, "school_id": school_id})
            
            # rss_feeds 삭제
            conn.execute(text("""
                DELETE FROM rss_feeds WHERE id = :rss_id
            """), {"rss_id": rss_feed_id})
            
            conn.commit()
            return True
            
    except Exception as e:
        st.error(f"RSS 피드 삭제 실패: {str(e)}")
        return False

def search_documents(query, vectorstore, engine, school_id=None):
    """개선된 문서 검색: 학교별 필터링 + 관련성 점수 계산"""
    try:
        results = []
        
        with engine.connect() as conn:
            # 학교별 필터링 쿼리
            school_filter = "AND d.school_id = :school_id" if school_id else ""
            params = {"query": f"%{query}%"}
            if school_id:
                params["school_id"] = school_id
            
            # 1. 키워드 기반 검색 (학교별 필터링)
            keyword_results = conn.execute(text(f"""
                SELECT dc.chunk_text, d.source_url, d.file_name, d.category, d.created_at,
                        ROW_NUMBER() OVER (ORDER BY d.created_at DESC) as rank
                FROM document_chunks dc
                JOIN documents d ON dc.document_id = d.id
                WHERE dc.chunk_text ILIKE :query {school_filter}
                ORDER BY d.created_at DESC
                LIMIT 10
            """), params).fetchall()
            
            # 2. 단어별 분해 검색 (유사도 향상)
            query_words = [word.strip() for word in query.split() if len(word.strip()) > 1]
            if len(query_words) > 1:
                word_conditions = " OR ".join([f"dc.chunk_text ILIKE :word_{i}" for i in range(len(query_words))])
                word_params = {f"word_{i}": f"%{word}%" for i, word in enumerate(query_words)}
                word_params.update({"original_query": f"%{query}%"})
                if school_id:
                    word_params["school_id"] = school_id
                
                similarity_results = conn.execute(text(f"""
                    SELECT dc.chunk_text, d.source_url, d.file_name, d.category, d.created_at,
                           ROW_NUMBER() OVER (ORDER BY d.created_at DESC) as rank
                    FROM document_chunks dc
                    JOIN documents d ON dc.document_id = d.id
                    WHERE ({word_conditions})
                    AND dc.chunk_text NOT ILIKE :original_query {school_filter}
                    ORDER BY d.created_at DESC
                    LIMIT 5
                """), word_params).fetchall()
            else:
                similarity_results = []
            
            # 3. 결과 합치기 및 중복 제거
            all_results = list(keyword_results) + list(similarity_results)
            seen_texts = set()
            unique_results = []
            
            for row in all_results:
                text_preview = row.chunk_text[:100]
                if text_preview not in seen_texts:
                    seen_texts.add(text_preview)
                    unique_results.append(row)
                
                if len(unique_results) >= 8:
                    break
            
            # 4. 관련성 점수 계산 및 Document 형태로 변환
            from langchain.schema import Document
            scored_results = []
            
            for i, row in enumerate(unique_results):
                title = extract_title_from_text(row.chunk_text)
                
                source_info = "RSS 공지사항"
                if row.category == 'pdf':
                    source_info = row.file_name or "PDF 문서"
                elif row.category == 'rss':
                    source_info = "RSS 공지사항"
                
                metadata = {
                    "source": row.source_url or "unknown",
                    "filename": source_info, 
                    "category": row.category or "unknown",
                    "date": row.created_at.strftime("%Y-%m-%d") if row.created_at else "N/A",
                    "title": title,
                    "rank": i + 1
                }
                
                # 관련성 점수 계산
                relevance_score = calculate_relevance_score(query, row.chunk_text, metadata)
                metadata["relevance_score"] = relevance_score
                
                scored_results.append({
                    'document': Document(page_content=row.chunk_text, metadata=metadata),
                    'score': relevance_score
                })
            
            # 5. 관련성 점수로 정렬 및 필터링
            scored_results.sort(key=lambda x: x['score'], reverse=True)
            
            # 6. 높은 관련성 결과만 반환 (임계값: 0.2로 하향 조정)
            high_relevance_results = []
            for item in scored_results:
                if item['score'] >= 0.2:  # 임계값 대폭 하향 조정
                    high_relevance_results.append(item['document'])
                if len(high_relevance_results) >= 5:  # 최대 5개
                    break
        
        return high_relevance_results
    except Exception as e:
        st.error(f"검색 실패: {str(e)}")
        return []

def process_rss_feed(rss_url, vectorstore, engine, embeddings=None, school_id=1):
    """RSS 피드를 처리하여 DB에 저장합니다 (rss_feeds 테이블 관리 포함)."""
    try:
        feed = feedparser.parse(rss_url)
        chunks_processed = 0
        skipped_duplicates = 0
        
        with engine.connect() as conn:
            # 1. RSS 피드를 rss_feeds 테이블에 등록 (없으면 추가)
            feed_title = feed.feed.get('title', rss_url)
            
            rss_feed_result = conn.execute(text("""
                INSERT INTO rss_feeds (school_id, url, title, status)
                VALUES (:school_id, :url, :title, 'active')
                ON CONFLICT (school_id, url) DO UPDATE SET
                    title = EXCLUDED.title,
                    last_processed = NOW()
                RETURNING id
            """), {
                "school_id": school_id,
                "url": rss_url,
                "title": feed_title
            }).fetchone()
            
            rss_feed_id = rss_feed_result[0]
            
            # 2. documents 테이블에서 RSS 문서 찾기/생성
            existing_doc = conn.execute(text("""
                SELECT id FROM documents 
                WHERE source_url = :source_url AND category = 'rss' AND school_id = :school_id
            """), {"source_url": rss_url, "school_id": school_id}).fetchone()
            
            if existing_doc:
                document_id = existing_doc[0]
            else:
                # 새 RSS 문서 생성
                result = conn.execute(text("""
                    INSERT INTO documents (school_id, source_url, category, processed, chunks_count)
                    VALUES (:school_id, :source_url, 'rss', FALSE, 0)
                    RETURNING id
                """), {"school_id": school_id, "source_url": rss_url})
                document_id = result.fetchone()[0]
            
            # 3. 기존 청크들의 제목과 링크 조회 (중복 확인용)
            existing_contents = conn.execute(text("""
                SELECT chunk_text FROM document_chunks 
                WHERE document_id = :document_id
            """), {"document_id": document_id}).fetchall()
            
            # 기존 제목들 추출 (중복 확인용)
            existing_titles = set()
            existing_links = set()
            for content_row in existing_contents:
                content = content_row[0]
                for line in content.split('\n'):
                    if line.strip().startswith('제목:'):
                        title = line.replace('제목:', '').strip()
                        existing_titles.add(title)
                    elif line.strip().startswith('링크:'):
                        link = line.replace('링크:', '').strip()
                        existing_links.add(link)
            
            # 4. RSS 항목들 처리 (중복 확인)
            for entry in feed.entries:
                entry_title = entry.get('title', '').strip()
                entry_link = entry.get('link', '').strip()
                
                # 중복 확인: 제목 또는 링크가 이미 존재하면 스킵
                if entry_title in existing_titles or entry_link in existing_links:
                    skipped_duplicates += 1
                    continue
                
                # 새로운 항목 처리
                content = f"""
제목: {entry_title}
내용: {entry.get('summary', entry.get('description', ''))}
링크: {entry_link}
발행일: {entry.get('published', '')}
                """
                
                splitter = CharacterTextSplitter.from_tiktoken_encoder(
                    separator="\n",
                    chunk_size=800,
                    chunk_overlap=100,
                )
                chunks = splitter.split_text(content)
                
                for chunk in chunks:
                    try:
                        embedding_vector = [0.0] * 1536  # 기본값
                        if embeddings:
                            try:
                                embedding_vector = embeddings.embed_query(chunk)
                            except:
                                pass
                        
                        conn.execute(text("""
                            INSERT INTO document_chunks (document_id, chunk_text, embedding)
                            VALUES (:document_id, :chunk_text, :embedding)
                        """), {
                            "document_id": document_id,
                            "chunk_text": chunk,
                            "embedding": embedding_vector
                        })
                        chunks_processed += 1
                        
                        existing_titles.add(entry_title)
                        existing_links.add(entry_link)
                        
                    except Exception as e:
                        st.warning(f"청크 저장 실패: {str(e)}")
                        continue
            
            # 5. documents 테이블 처리 상태 업데이트
            total_chunks = conn.execute(text("""
                SELECT COUNT(*) FROM document_chunks WHERE document_id = :document_id
            """), {"document_id": document_id}).fetchone()[0]
            
            conn.execute(text("""
                UPDATE documents 
                SET processed = TRUE, chunks_count = :chunks_count
                WHERE id = :document_id
            """), {
                "document_id": document_id,
                "chunks_count": total_chunks
            })
            
            # 6. rss_feeds 테이블 처리 상태 업데이트
            conn.execute(text("""
                UPDATE rss_feeds 
                SET last_processed = NOW(), processed_count = :processed_count
                WHERE id = :rss_feed_id
            """), {
                "rss_feed_id": rss_feed_id,
                "processed_count": total_chunks
            })
            
            conn.commit()
        
        if skipped_duplicates > 0:
            st.info(f"📊 처리 결과: 신규 {chunks_processed}개 청크 추가, 중복 {skipped_duplicates}개 항목 스킵")
        
        return chunks_processed
    except Exception as e:
        st.error(f"RSS 피드 처리 실패: {str(e)}")
        return 0
    """RSS 피드를 처리하여 DB에 저장합니다 (school_id 포함)."""
    try:
        feed = feedparser.parse(rss_url)
        chunks_processed = 0
        skipped_duplicates = 0
        
        with engine.connect() as conn:
            # 1. 기존 RSS 문서가 있는지 확인
            existing_doc = conn.execute(text("""
                SELECT id FROM documents 
                WHERE source_url = :source_url AND category = 'rss' AND school_id = :school_id
            """), {"source_url": rss_url, "school_id": school_id}).fetchone()
            
            if existing_doc:
                document_id = existing_doc[0]
            else:
                # 새 RSS 문서 생성
                result = conn.execute(text("""
                    INSERT INTO documents (school_id, source_url, category, processed, chunks_count)
                    VALUES (:school_id, :source_url, 'rss', FALSE, 0)
                    RETURNING id
                """), {"school_id": school_id, "source_url": rss_url})
                document_id = result.fetchone()[0]
            
            # 기존 청크들의 제목과 링크 조회 (중복 확인용)
            existing_contents = conn.execute(text("""
                SELECT chunk_text FROM document_chunks 
                WHERE document_id = :document_id
            """), {"document_id": document_id}).fetchall()
            
            # 기존 제목들 추출 (중복 확인용)
            existing_titles = set()
            existing_links = set()
            for content_row in existing_contents:
                content = content_row[0]
                for line in content.split('\n'):
                    if line.strip().startswith('제목:'):
                        title = line.replace('제목:', '').strip()
                        existing_titles.add(title)
                    elif line.strip().startswith('링크:'):
                        link = line.replace('링크:', '').strip()
                        existing_links.add(link)
            
            # RSS 항목들 처리 (중복 확인)
            for entry in feed.entries:
                entry_title = entry.get('title', '').strip()
                entry_link = entry.get('link', '').strip()
                
                # 중복 확인: 제목 또는 링크가 이미 존재하면 스킵
                if entry_title in existing_titles or entry_link in existing_links:
                    skipped_duplicates += 1
                    continue
                
                # 새로운 항목 처리
                content = f"""
제목: {entry_title}
내용: {entry.get('summary', entry.get('description', ''))}
링크: {entry_link}
발행일: {entry.get('published', '')}
                """
                
                splitter = CharacterTextSplitter.from_tiktoken_encoder(
                    separator="\n",
                    chunk_size=800,
                    chunk_overlap=100,
                )
                chunks = splitter.split_text(content)
                
                for chunk in chunks:
                    try:
                        embedding_vector = [0.0] * 1536  # 기본값
                        if embeddings:
                            try:
                                embedding_vector = embeddings.embed_query(chunk)
                            except:
                                pass
                        
                        conn.execute(text("""
                            INSERT INTO document_chunks (document_id, chunk_text, embedding)
                            VALUES (:document_id, :chunk_text, :embedding)
                        """), {
                            "document_id": document_id,
                            "chunk_text": chunk,
                            "embedding": embedding_vector
                        })
                        chunks_processed += 1
                        
                        existing_titles.add(entry_title)
                        existing_links.add(entry_link)
                        
                    except Exception as e:
                        st.warning(f"청크 저장 실패: {str(e)}")
                        continue
            
            # 처리 상태 업데이트
            total_chunks = conn.execute(text("""
                SELECT COUNT(*) FROM document_chunks WHERE document_id = :document_id
            """), {"document_id": document_id}).fetchone()[0]
            
            conn.execute(text("""
                UPDATE documents 
                SET processed = TRUE, chunks_count = :chunks_count
                WHERE id = :document_id
            """), {
                "document_id": document_id,
                "chunks_count": total_chunks
            })
            
            conn.commit()
        
        if skipped_duplicates > 0:
            st.info(f"📊 처리 결과: 신규 {chunks_processed}개 청크 추가, 중복 {skipped_duplicates}개 항목 스킵")
        
        return chunks_processed
    except Exception as e:
        st.error(f"RSS 피드 처리 실패: {str(e)}")
        return 0

def delete_document_from_db(document_id, engine):
    """파일 메타데이터를 documents 테이블에 저장합니다."""
    try:
        with engine.connect() as conn:
            # source_url로 기존 문서 확인
            source_url = s3_key if s3_key.startswith('s3://') else f"s3://{S3_BUCKET_NAME}/{s3_key}"
            
            existing_doc = conn.execute(text("""
                SELECT id FROM documents 
                WHERE source_url = :source_url OR file_name = :filename
            """), {"source_url": source_url, "filename": filename}).fetchone()
            
            if not existing_doc:
                # 새 문서만 저장 (중복 방지)
                conn.execute(text("""
                    INSERT INTO documents (school_id, file_name, source_url, category, processed, chunks_count)
                    VALUES (1, :filename, :source_url, :doc_type, FALSE, 0)
                """), {
                    "filename": filename,
                    "source_url": source_url,
                    "doc_type": doc_type
                })
                conn.commit()
        return True
    except Exception as e:
        st.error(f"메타데이터 저장 실패: {str(e)}")
        return False

def delete_document_from_db(document_id, engine):
    """문서를 DB에서 완전히 삭제합니다 (document_chunks + documents)."""
    try:
        with engine.connect() as conn:
            # 1. 먼저 document_chunks에서 삭제 (Foreign Key 때문에)
            chunks_result = conn.execute(text("""
                DELETE FROM document_chunks 
                WHERE document_id = :document_id
            """), {"document_id": document_id})
            
            # 2. documents 테이블에서 삭제
            docs_result = conn.execute(text("""
                DELETE FROM documents 
                WHERE id = :document_id
            """), {"document_id": document_id})
            
            conn.commit()
            
            return chunks_result.rowcount, docs_result.rowcount
    except Exception as e:
        st.error(f"문서 삭제 실패: {str(e)}")
        return 0, 0

def extract_title_from_text(text):
    """텍스트에서 제목을 추출합니다."""
    lines = text.split('\n')
    for line in lines:
        line = line.strip()
        if line and '제목:' in line:
            return line.replace('제목:', '').strip()
        elif line and len(line) > 10 and len(line) < 100:
            # 첫 번째 의미있는 줄을 제목으로 간주
            return line
    return text[:50] + "..." if len(text) > 50 else text

# 자연어 쿼리 전처리 함수
def preprocess_query(query):
    """자연어 쿼리에서 핵심 키워드를 추출합니다."""
    try:
        # 불용어 제거
        stopwords = ['에', '대해', '대한', '에서', '으로', '로', '이', '가', '을', '를', '은', '는', 
                    '궁금합니다', '궁금해요', '알고싶어요', '알려주세요', '문의', '질문', 
                    '어떻게', '언제', '어디서', '무엇', '왜', '어떤', '입니다', '해주세요',
                    '중에서', '관련해서', '관련하여', '에 관해', '에 관한', '것', '수', '있', '없']
        
        # 핵심 키워드 추출
        words = re.sub(r'[^\w가-힣\s]', ' ', query).split()
        core_keywords = []
        
        for word in words:
            word = word.strip()
            if len(word) > 1 and word not in stopwords:
                core_keywords.append(word)
        
        # 원본 쿼리와 핵심 키워드 조합 반환
        core_query = ' '.join(core_keywords)
        
        return {
            'original': query,
            'processed': core_query,
            'keywords': core_keywords
        }
    except:
        return {
            'original': query,
            'processed': query,
            'keywords': query.split()
        }

def calculate_keyword_score(query, document_content):
    """키워드 매칭 점수 계산 (전처리된 쿼리 사용)"""
    try:
        # 쿼리 전처리
        query_data = preprocess_query(query)
        original_query = query_data['original'].lower()
        processed_query = query_data['processed'].lower()
        core_keywords = set([kw.lower() for kw in query_data['keywords']])
        
        doc_text = document_content.lower()
        doc_words = set(re.sub(r'[^\w가-힣]', ' ', doc_text).split())
        
        if not core_keywords:
            return 0.0
            
        # 1. 핵심 키워드 매칭 점수
        matched_keywords = core_keywords.intersection(doc_words)
        keyword_ratio = len(matched_keywords) / len(core_keywords) if core_keywords else 0
        
        # 2. 구문 매칭 보너스 (원본 쿼리와 전처리된 쿼리 모두 확인)
        phrase_bonus = 0
        if original_query.strip() in doc_text:
            phrase_bonus += 0.4
        elif processed_query.strip() in doc_text:
            phrase_bonus += 0.3
        
        # 3. 핵심 키워드별 개별 매칭 보너스
        individual_bonus = 0
        for keyword in core_keywords:
            if len(keyword) > 2 and keyword in doc_text:
                individual_bonus += 0.15
        
        # 4. 연속 키워드 매칭 (예: "교원연수" → "교원" + "연수")
        sequence_bonus = 0
        if len(core_keywords) >= 2:
            keyword_list = list(core_keywords)
            for i in range(len(keyword_list)-1):
                combined = keyword_list[i] + keyword_list[i+1]
                if combined in doc_text:
                    sequence_bonus += 0.2
        
        final_score = keyword_ratio + phrase_bonus + individual_bonus + sequence_bonus
        return min(final_score, 1.0)
        
    except:
        return 0.0

def calculate_category_score(query, document_content, metadata):
    """카테고리 및 특수 키워드 점수 계산 (전처리된 쿼리 사용)"""
    try:
        # 쿼리 전처리
        query_data = preprocess_query(query)
        core_keywords = [kw.lower() for kw in query_data['keywords']]
        content_lower = document_content.lower()
        
        # 기본 점수를 높게 시작
        base_score = 0.8
        
        # 카테고리별 키워드 그룹 정의 (확장)
        category_groups = {
            '교원관리': {
                'keywords': ['교원', '교수', '연수', '초빙', '채용', '인사', '학술', '연구'],
                'negative': []
            },
            '일반_입학': {
                'keywords': ['입학', '신입생', '모집', '지원', '전형', '수시', '정시', '입시상담'],
                'negative': ['위탁', '산업체위탁교육']
            },
            '특수_입학': {
                'keywords': ['위탁교육', '산업체', '편입', '전공심화', '재입학'],
                'negative': []
            },
            '학사관리': {
                'keywords': ['수강신청', '학적', '성적', '졸업', '휴학', '복학', '규정'],
                'negative': []
            },
            '학생활동': {
                'keywords': ['gem-festival', 'festival', '축제', '동아리', '행사'],
                'negative': []
            },
            '학생지원': {
                'keywords': ['장학금', '취업', '상담', '복지'],
                'negative': []
            }
        }
        
        max_score = base_score
        
        for category, rules in category_groups.items():
            score = base_score
            matched_positive = 0
            
            # 핵심 키워드와 카테고리 키워드 매칭
            for category_kw in rules['keywords']:
                for core_kw in core_keywords:
                    if category_kw in core_kw or core_kw in category_kw:
                        if category_kw in content_lower:
                            matched_positive += 1
                            score += 0.15
            
            # 매칭된 키워드가 많으면 추가 보너스
            if matched_positive >= 2:
                score += 0.1
            
            # 부정 키워드 체크 (더 엄격하게)
            for neg_keyword in rules['negative']:
                if neg_keyword in content_lower and not any(neg_keyword in ck for ck in core_keywords):
                    score -= 0.25
            
            max_score = max(max_score, score)
        
        return max(min(max_score, 1.0), 0.0)
    except:
        return 0.8

def calculate_context_score(query, document_content):
    """문맥적 유사도 점수 계산 (쿼리 길이에 관계없이 일관성 유지)"""
    try:
        # 쿼리 전처리
        query_data = preprocess_query(query)
        core_keywords = query_data['keywords']
        
        # 기본 점수 (쿼리 길이와 무관하게 일정하게)
        base_score = 0.85
        
        # 문서 품질 평가
        doc_length = len(document_content.split())
        length_score = 1.0
        
        if doc_length < 5:
            length_score = 0.6
        elif doc_length > 1000:
            length_score = 0.9
            
        # 정보 제공성 평가
        info_indicators = ['안내', '공지', '알림', '일정', '방법', '절차', '신청', '규정', '지침']
        has_info_content = any(indicator in document_content for indicator in info_indicators)
        info_bonus = 0.1 if has_info_content else 0
        
        final_score = (base_score + info_bonus) * length_score
        return min(final_score, 1.0)
        
    except:
        return 0.85

# 관련성 점수 계산 함수들
def calculate_relevance_score(query, document_content, metadata):
    """하이브리드 관련성 점수 계산 (자연어 쿼리 최적화 버전)"""
    try:
        # 각 점수 계산
        keyword_score = calculate_keyword_score(query, document_content)
        category_score = calculate_category_score(query, document_content, metadata)
        context_score = calculate_context_score(query, document_content)
        
        # 가중 평균 (키워드에 더 높은 가중치, 자연어 친화적)
        final_score = (keyword_score * 0.65) + (category_score * 0.25) + (context_score * 0.10)
        
        # 자연어 문장에 대한 추가 보너스
        query_data = preprocess_query(query)
        if len(query_data['original'].split()) > 3:  # 자연어 문장인 경우
            # 키워드 밀도가 높으면 보너스
            keyword_density = len(query_data['keywords']) / len(query_data['original'].split())
            if keyword_density > 0.5:
                final_score = min(final_score + 0.1, 1.0)
        
        return round(final_score, 3)
    except Exception as e:
        print(f"관련성 점수 계산 실패: {str(e)}")
        return 0.5

def get_relevance_indicator(score):
    """점수에 따른 관련성 지시자 반환 (조정된 임계값)"""
    if score >= 0.75:
        return "✅", "높음", "success"
    elif score >= 0.50:
        return "⚠️", "보통", "warning"
    else:
        return "❌", "낮음", "error"

# 부서 검색 fallback 함수들
def find_relevant_department(query, school_id, engine):
    """
    질문에서 키워드를 추출하여 관련 부서를 찾습니다.
    가중치 기반 점수 계산으로 가장 적합한 부서를 반환합니다.
    """
    try:
        with engine.connect() as conn:
            # 부서별 키워드와 직원 정보 조회
            result = conn.execute(text("""
                SELECT 
                    d.id, d.name, d.description, d.main_phone,
                    bk.keyword, bk.weight,
                    s.name as staff_name, s.position, s.phone, s.email, 
                    s.responsibilities, s.is_head
                FROM departments d 
                LEFT JOIN business_keywords bk ON d.id = bk.department_id
                LEFT JOIN staff_members s ON d.id = s.department_id AND s.is_head = TRUE
                WHERE d.school_id = :school_id
                ORDER BY d.name, bk.weight DESC
            """), {"school_id": school_id}).fetchall()
            
            if not result:
                return None
                
            # 질문 전처리 (소문자 변환 및 공백 제거)
            query_processed = re.sub(r'[^\w가-힣]', ' ', query.lower()).strip()
            query_words = query_processed.split()
            
            # 부서별 점수 계산
            department_scores = {}
            department_info = {}
            
            for row in result:
                dept_id = row[0]
                dept_name = row[1]
                keyword = row[4]
                weight = row[5] if row[5] else 1
                
                # 부서 정보 저장 (처음 한 번만)
                if dept_id not in department_info:
                    department_info[dept_id] = {
                        'name': dept_name,
                        'description': row[2],
                        'main_phone': row[3],
                        'staff_name': row[6],
                        'staff_position': row[7],
                        'staff_phone': row[8],
                        'staff_email': row[9],
                        'staff_responsibilities': row[10]
                    }
                
                # 키워드 매칭 점수 계산
                if keyword and dept_id not in department_scores:
                    department_scores[dept_id] = 0
                
                if keyword:
                    keyword_lower = keyword.lower()
                    # 완전 매칭 (높은 점수)
                    if keyword_lower in query_processed:
                        department_scores[dept_id] += weight * 3
                    # 부분 매칭 (중간 점수)
                    elif any(word in keyword_lower or keyword_lower in word for word in query_words):
                        department_scores[dept_id] += weight * 2
                    # 유사 키워드 매칭 (낮은 점수)
                    elif any(is_similar_keyword(word, keyword_lower) for word in query_words):
                        department_scores[dept_id] += weight
            
            # 점수가 높은 부서 반환
            if department_scores:
                best_dept_id = max(department_scores.items(), key=lambda x: x[1])
                if best_dept_id[1] > 0:  # 점수가 0보다 큰 경우만
                    return department_info[best_dept_id[0]]
            
        return None
    except Exception as e:
        print(f"부서 검색 실패: {str(e)}")
        return None

def is_similar_keyword(word, keyword):
    """유사한 키워드인지 판단하는 함수"""
    similar_pairs = [
        (['등록금', '학비', '납부금'], ['등록금', '납부']),
        (['수강신청', '수강', '강의신청'], ['수강신청', '수업관리']),
        (['성적', '학점', '점수'], ['성적']),
        (['졸업', '졸업요건', '학위'], ['졸업']),
        (['휴학', '휴학신청'], ['휴학']),
        (['복학', '복학신청'], ['복학']),
        (['장학금', '장학', '지원금'], ['장학금']),
        (['취업', '취업지원', '일자리'], ['취업', '진로']),
        (['입학', '입시', '신입생'], ['입학', '입시', '모집']),
        (['실습', '현장실습', '인턴십'], ['현장실습', '실험실습']),
        (['상담', '심리상담', '학생상담'], ['심리상담', '학생상담']),
        (['시설', '건물', '공사'], ['시설', '공사']),
        (['인사', '인사관리', '직원'], ['인사']),
        (['예산', '회계', '재정'], ['예산', '회계'])
    ]
    
    for word_group, keyword_group in similar_pairs:
        if word in word_group and keyword in keyword_group:
            return True
    return False

def display_search_results(search_results):
    """검색 결과를 관련성 점수와 함께 명확하게 표시합니다."""
    if not search_results:
        return
    
    st.write(f"🎯 **검색 결과: {len(search_results)}개 관련 항목 발견**")
    
    # 관련성 점수 통계 표시
    scores = [doc.metadata.get('relevance_score', 0.0) for doc in search_results]
    if scores:
        avg_score = sum(scores) / len(scores)
        max_score = max(scores)
        min_score = min(scores)
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("평균 관련성", f"{avg_score:.1%}")
        with col2:
            st.metric("최고 관련성", f"{max_score:.1%}")
        with col3:
            st.metric("최저 관련성", f"{min_score:.1%}")
    
    st.write("")
    
    # 항목별로 관련성 점수와 함께 표시
    for i, doc in enumerate(search_results, 1):
        title = doc.metadata.get('title', '제목 없음')
        date = doc.metadata.get('date', 'N/A')
        source = doc.metadata.get('filename', 'N/A')
        relevance_score = doc.metadata.get('relevance_score', 0.0)
        
        # 관련성 지시자
        indicator, level, alert_type = get_relevance_indicator(relevance_score)
        
        # 관련성에 따른 스타일링
        if alert_type == "success":
            container_type = st.success
        elif alert_type == "warning":
            container_type = st.warning
        else:
            container_type = st.error
            
        # 펼쳐지는 박스로 표시 (관련성 점수 포함)
        with st.expander(f"{indicator} **항목 {i}**: {title} | 관련성: {relevance_score:.1%} ({level})"):
            # 관련성 점수에 따른 추가 안내
            if relevance_score >= 0.85:
                st.success(f"🎯 **높은 관련성** ({relevance_score:.1%}) - 매우 신뢰할 만한 정보입니다.")
            elif relevance_score >= 0.60:
                st.warning(f"⚠️ **보통 관련성** ({relevance_score:.1%}) - 참고용으로 활용하세요.")
            else:
                st.error(f"❌ **낮은 관련성** ({relevance_score:.1%}) - 다른 질문을 시도해보세요.")
            
            st.write(f"**📅 날짜**: {date}")
            st.write(f"**📂 출처**: {source}")
            st.write("**📄 내용**:")
            
            # 관련성이 낮으면 내용을 축약해서 표시
            if relevance_score < 0.60:
                preview = doc.page_content[:150] + "..." if len(doc.page_content) > 150 else doc.page_content
                st.text(preview)
                st.caption("⚠️ 관련성이 낮아 축약된 내용만 표시됩니다.")
            else:
                preview = doc.page_content[:300] + "..." if len(doc.page_content) > 300 else doc.page_content
                st.text(preview)

    # 전체적인 관련성 경고
    if scores and max(scores) < 0.60:
        st.error("⚠️ **주의**: 모든 검색 결과의 관련성이 낮습니다. 부서 문의를 권장합니다.")
    elif scores and avg_score < 0.50:
        st.warning("⚠️ **주의**: 평균 관련성이 낮습니다. 검색어를 다르게 시도해보세요.")

def generate_ai_response(query, bedrock, search_results=None):
    """AI 응답을 생성합니다. 검색 결과 기반으로 답변합니다."""
    try:
        if search_results and len(search_results) > 0:
            # 검색 결과가 있는 경우 RAG 응답
            context = "\n".join([doc.page_content for doc in search_results])
            
            # 출처 정보 정리
            sources = []
            for i, doc in enumerate(search_results, 1):
                title = doc.metadata.get('title', 'N/A')
                date = doc.metadata.get('date', 'N/A')
                sources.append(f"[항목 {i}] {title} ({date})")
            
            sources_text = "\n".join(sources)
            
            prompt = f"""다음은 학사 정보에 대한 질문과 관련 문서 내용입니다:

질문: {query}

관련 문서 내용:
{context}

위 내용을 바탕으로 질문에 대해 명확하고 친절하게 한국어로 답변해주세요. 
문서에 없는 내용은 언급하지 말고, 확실한 정보만 답변에 포함해주세요.
가능하면 구체적인 절차나 조건도 함께 알려주세요.

중요: 답변 마지막에 반드시 다음 형식으로 참고 자료를 명시해주세요:

📋 **참고 자료:**
{sources_text}"""
        else:
            # 검색 결과가 없는 경우 일반 AI 응답
            prompt = f"""사용자 질문: {query}

친근하고 도움이 되는 AI 어시스턴트로서 답변해주세요. 
한국어로 자연스럽게 대화하면서 도움을 제공해주세요.

만약 학사 정보와 관련된 질문이라면, 현재 관련 문서를 찾을 수 없다고 안내하고 
연성대학교 공식 홈페이지에서 확인하라고 안내해주세요."""
        
        # boto3 bedrock-runtime에서 Nova 모델의 정확한 형식 사용
        response = bedrock.invoke_model(
            modelId="us.amazon.nova-lite-v1:0",
            contentType="application/json",
            accept="application/json",
            body=json.dumps({
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "text": prompt
                            }
                        ]
                    }
                ],
                "inferenceConfig": {
                    "maxTokens": 4000,
                    "temperature": 0.7
                }
            })
        )
        
        # 응답 파싱 - Nova 모델의 응답 형식
        response_body = json.loads(response['body'].read())
        
        # Nova 응답 구조: {"output": {"message": {"content": [{"text": "답변"}]}}}
        if 'output' in response_body and 'message' in response_body['output']:
            content = response_body['output']['message'].get('content', [])
            if content and len(content) > 0:
                return content[0].get('text', '응답을 생성할 수 없습니다.')
        
        return response_body.get('outputText', '응답을 생성할 수 없습니다.')
        
    except Exception as e:
        return f"죄송합니다. AI 응답 생성 중 오류가 발생했습니다: {str(e)}"

# S3 파일과 DB 메타데이터를 동시에 삭제하는 함수 (delete_document_from_db 함수가 document_id로 삭제하도록 위에 수정됨)
def delete_file_from_s3_and_db(engine, s3_client, bucket_name, document_id):
    """DB에 있는 문서 메타데이터와 S3의 실제 파일을 삭제합니다."""
    try:
        # 1. DB에서 source_url (S3 key) 조회
        with engine.connect() as conn:
            result = conn.execute(text("SELECT source_url FROM documents WHERE id = :document_id"),
                                  {"document_id": document_id}).fetchone()
            
            if not result:
                st.error("DB에서 문서를 찾을 수 없습니다.")
                return False
                
            source_url = result[0]
            
            # 2. S3 Key 추출
            s3_key = source_url.replace(f"s3://{bucket_name}/", "")
            
            # 3. S3 파일 삭제
            if s3_key and not source_url.startswith("rss"): # RSS는 S3 파일이 없으므로 스킵
                 s3_client.delete_object(Bucket=bucket_name, Key=s3_key)
                 st.info(f"S3 파일 삭제: {s3_key}")
            
            # 4. DB에서 문서 메타데이터 및 청크 삭제
            chunks_deleted, docs_deleted = delete_document_from_db(document_id, engine)

            if docs_deleted > 0:
                return True
            else:
                st.error("DB 문서 메타데이터 삭제 실패")
                return False
                
    except Exception as e:
        st.error(f"S3 및 DB 삭제 실패: {str(e)}")
        return False


# 메인 애플리케이션
def main():
    # AWS 클라이언트 초기화
    bedrock_client, embeddings, s3_client = init_aws_clients()
    if not bedrock_client:
        st.error("Bedrock 클라이언트 초기화에 실패했습니다. EC2 IAM 역할을 확인해주세요.")
        return
    
    # PostgreSQL 엔진 초기화
    engine = init_postgresql_vectorstore()
    if not engine:
        return
    
    # 학교 선택 UI (전체 앱 상단)
    school_id, selected_school = render_school_selector(engine)
    
    # 선택된 학교 통계 표시
    stats = get_school_stats(engine, school_id)
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("📄 총 문서", stats["total_documents"])
    with col2:
        st.metric("✅ 처리 완료", stats["processed_documents"])
    with col3:
        st.metric("📊 총 청크", stats["total_chunks"])
    
    st.divider()
    
    # 벡터 스토어 초기화 (임베딩이 있는 경우)
    vectorstore = init_pgvector(embeddings, engine) if embeddings else None
    
    st.success("✅ 시스템이 성공적으로 초기화되었습니다!")
    if not vectorstore:
        st.info("💬 일반 AI 챗봇 + 텍스트 검색 모드로 작동합니다.")
    else:
        st.success("🔍 벡터 검색 + AI 챗봇 모드로 작동합니다.")
    
    # 탭 생성
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "💬 챗봇", "📄 PDF 업로드", "📡 S3 PDF 관리", "🔗 RSS 피드", "📊 파일 관리"
    ])
    
    # 탭 1: 챗봇
    with tab1:
        st.header("💬 학사 정보 챗봇")
        st.info(f"📚 **{selected_school}** 관련 질문에 답변해드립니다!")
        
        search_query = st.text_input(
            "궁금한 내용을 자연어로 입력하세요:",
            placeholder="예: 장학금 신청 방법 / 입학 관련 정보 / 졸업 요건",
            key=f"search_query_{school_id}"
        )
        
        if search_query:
            with st.spinner("문서 검색 및 답변 생성 중..."):
                # 선택된 학교의 문서에서만 검색
                search_results = search_documents(search_query, vectorstore, engine, school_id)
                
                # 관련성 점수 기반 필터링
                high_quality_results = []
                if search_results:
                    for doc in search_results:
                        relevance_score = doc.metadata.get('relevance_score', 0.0)
                        if relevance_score >= 0.50:  # 임계값: 50%로 하향 조정
                            high_quality_results.append(doc)
                
                if high_quality_results:
                    # RAG 기반 응답 (고품질 결과만)
                    st.success("📚 문서 기반 답변")
                    
                    # 평균 관련성 점수 표시
                    avg_relevance = sum(doc.metadata.get('relevance_score', 0.0) for doc in high_quality_results) / len(high_quality_results)
                    st.info(f"📊 평균 관련성: {avg_relevance:.1%} | 총 {len(high_quality_results)}개 문서 참조")
                    
                    display_search_results(high_quality_results)
                    st.write("---")
                    
                    # AI 응답 생성
                    ai_response = generate_ai_response(search_query, bedrock_client, high_quality_results)
                    st.subheader("🤖 AI 응답")
                    st.markdown(ai_response)
                
                elif search_results:
                    # 검색 결과는 있지만 관련성이 낮은 경우
                    st.warning("⚠️ 검색된 문서의 관련성이 낮습니다")
                    
                    avg_relevance = sum(doc.metadata.get('relevance_score', 0.0) for doc in search_results) / len(search_results)
                    st.write(f"📊 평균 관련성: {avg_relevance:.1%} (임계값: 60% 미만)")
                    
                    # 낮은 관련성 결과도 참고용으로 표시
                    with st.expander("🔍 낮은 관련성 검색 결과 (참고용)"):
                        display_search_results(search_results)
                    
                    # Fallback: 부서 검색
                    department = find_relevant_department(search_query, school_id, engine)
                    
                    if department:
                        # 부서 매칭된 경우
                        st.info("📞 담당 부서 안내")
                        
                        contact_info = f"📞 **{department['name']}**\n"
                        
                        if department['staff_name']:
                            contact_info += f"• 담당자: {department['staff_name']} ({department['staff_position']})\n"
                        
                        if department['staff_phone']:
                            contact_info += f"• 전화번호: {department['staff_phone']}\n"
                        elif department['main_phone']:
                            contact_info += f"• 대표번호: {department['main_phone']}\n"
                            
                        if department['staff_email']:
                            contact_info += f"• 이메일: {department['staff_email']}\n"
                            
                        if department['staff_responsibilities']:
                            contact_info += f"• 담당업무: {department['staff_responsibilities']}\n"
                        
                        contact_info += f"• 업무시간: 평일 9시~18시"
                        
                        fallback_response = f"""📚 **'{search_query}'**에 대한 관련성 높은 문서를 찾을 수 없습니다.

하지만 관련 업무는 다음 부서에서 담당하고 있습니다:

{contact_info}

이 부서로 직접 문의하시면 더 정확하고 상세한 답변을 받으실 수 있습니다."""
                        
                        st.markdown(fallback_response)
                        st.caption("💡 관련성이 낮은 문서보다는 해당 부서로 직접 문의하시기 바랍니다.")
                        
                    else:
                        # 매칭되는 부서도 없는 경우
                        general_response = f"""📚 **'{search_query}'**에 대한 문서를 찾을 수 없습니다.

**{selected_school}** 일반 학사 문의는 다음으로 연락해주세요:

📞 **교무처 (학사업무 총괄)**
• 전화번호: 441-1066
• 이메일: hhlee@yeonsung.ac.kr
• 업무시간: 평일 9시~18시

또는 해당 학과 사무실로 직접 문의하시기 바랍니다."""
                        
                        st.markdown(general_response)
                        st.caption("💡 구체적인 질문은 관련 학과나 부서로 직접 문의하시면 더 정확한 답변을 받으실 수 있습니다.")
                
                else:
                    # 검색 결과 없음 - 바로 Fallback
                    department = find_relevant_department(search_query, school_id, engine)
                    
                    if department:
                        # 부서 매칭된 경우
                        st.info("📞 담당 부서 안내")
                        
                        contact_info = f"📞 **{department['name']}**\n"
                        
                        if department['staff_name']:
                            contact_info += f"• 담당자: {department['staff_name']} ({department['staff_position']})\n"
                        
                        if department['staff_phone']:
                            contact_info += f"• 전화번호: {department['staff_phone']}\n"
                        elif department['main_phone']:
                            contact_info += f"• 대표번호: {department['main_phone']}\n"
                            
                        if department['staff_email']:
                            contact_info += f"• 이메일: {department['staff_email']}\n"
                            
                        if department['staff_responsibilities']:
                            contact_info += f"• 담당업무: {department['staff_responsibilities']}\n"
                        
                        contact_info += f"• 업무시간: 평일 9시~18시"
                        
                        fallback_response = f"""📚 **'{search_query}'**에 대한 문서를 찾을 수 없습니다.

하지만 관련 업무는 다음 부서에서 담당하고 있습니다:

{contact_info}

이 부서로 직접 문의하시면 더 정확하고 상세한 답변을 받으실 수 있습니다."""
                        
                        st.markdown(fallback_response)
                        st.caption("💡 문서에서 찾을 수 없는 질문은 해당 부서로 직접 문의하시기 바랍니다.")
                        
                    else:
                        # 매칭되는 부서가 없는 경우
                        st.warning("❓ 일반 문의 안내")
                        
                        general_response = f"""📚 **'{search_query}'**에 대한 문서를 찾을 수 없습니다.

**{selected_school}** 일반 학사 문의는 다음으로 연락해주세요:

📞 **교무처 (학사업무 총괄)**
• 전화번호: 441-1066
• 이메일: hhlee@yeonsung.ac.kr
• 업무시간: 평일 9시~18시

또는 해당 학과 사무실로 직접 문의하시기 바랍니다."""
                        
                        st.markdown(general_response)
                        st.caption("💡 구체적인 질문은 관련 학과나 부서로 직접 문의하시면 더 정확한 답변을 받으실 수 있습니다.")

    
    # 탭 2: PDF 업로드
    with tab2:
        st.header("📄 PDF 파일 업로드")
        st.info(f"🤖 **{selected_school}**에 자동으로 업로드됩니다. PDF가 Lambda 함수에 의해 자동 벡터화 처리됩니다!")
        
        uploaded_files = st.file_uploader(
            "PDF 파일을 선택하세요 (업로드하면 자동으로 처리 시작)",
            type=['pdf'],
            accept_multiple_files=True,
            key=f"pdf_uploader_{school_id}_{st.session_state.get(f'uploader_reset_{school_id}', 0)}"  # 동적 키
        )
        
        if uploaded_files:
            for uploaded_file in uploaded_files:
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    st.write(f"파일명: {uploaded_file.name}")
                    st.write(f"크기: {uploaded_file.size:,} bytes")
                
                with col2:
                    if st.button(f"업로드", key=f"upload_{uploaded_file.name}_{school_id}"):
                        with st.spinner("업로드 중..."):
                            # 학교별 S3 키 생성
                            school_code = get_school_code_by_id(engine, school_id)
                            s3_key = f"documents/{school_code}/{datetime.now().strftime('%Y/%m/%d')}/{uploaded_file.name}"
                            
                            # S3 업로드
                            if upload_to_s3(uploaded_file, s3_client, S3_BUCKET_NAME, s3_key):
                                # 메타데이터 저장 (school_id 포함)
                                if save_file_metadata(engine, uploaded_file.name, s3_key, "pdf", school_id):
                                    st.success(f"✅ {uploaded_file.name} 업로드 완료!")
                                    st.info("🤖 **자동 처리**: PDF가 Lambda 함수에 의해 자동으로 벡터화 처리됩니다.")
                                    st.caption("💡 S3 PDF 처리 탭에서 처리 상태를 확인할 수 있습니다.")
                                    
                                    # 2초 후 자동 새로고침
                                    st.info("🔄 2초 후 페이지가 자동으로 새로고침됩니다...")
                                    import time
                                    time.sleep(2)
                                    
                                    # file_uploader 완전 초기화를 위한 키 리셋
                                    current_reset = st.session_state.get(f'uploader_reset_{school_id}', 0)
                                    st.session_state[f'uploader_reset_{school_id}'] = current_reset + 1
                                    
                                    # 기존 관련 세션 상태 정리
                                    keys_to_delete = []
                                    for key in st.session_state.keys():
                                        if f"pdf_uploader_{school_id}_" in str(key) and str(current_reset) in str(key):
                                            keys_to_delete.append(key)
                                    
                                    for key in keys_to_delete:
                                        del st.session_state[key]
                                    
                                    st.rerun()
                                else:
                                    st.error("메타데이터 저장 실패")
                            else:
                                st.error("S3 업로드 실패")
    
    # 탭 3: S3 PDF 관리
    with tab3:
        st.header(f"📡 S3 PDF 관리 - {selected_school}")
        st.info("업로드된 PDF 파일들을 벡터화하거나 삭제할 수 있습니다.")
        
        # 파일 목록 조회 (school_id 필터링 적용)
        file_metadata = get_file_metadata(engine, school_id)
        
        if not file_metadata.empty:
            st.subheader("📊 업로드된 파일 목록")
            
            # 페이지네이션 설정
            page_size = 5  # 한 페이지당 파일 수
            total_files = len(file_metadata)
            total_pages = (total_files - 1) // page_size + 1
            
            # 페이지 선택 UI
            if total_pages > 1:
                col1, col2, col3 = st.columns([1, 2, 1])
                with col2:
                    current_page = st.selectbox(
                        "페이지 선택",
                        range(1, total_pages + 1),
                        format_func=lambda x: f"페이지 {x} / {total_pages}",
                        key=f"pdf_page_{school_id}"
                    )
                    st.caption(f"총 {total_files}개 파일 중 {(current_page-1)*page_size + 1}~{min(current_page*page_size, total_files)}개 표시")
            else:
                current_page = 1
            
            # 현재 페이지 파일들 추출
            start_idx = (current_page - 1) * page_size
            end_idx = min(start_idx + page_size, total_files)
            current_page_files = file_metadata.iloc[start_idx:end_idx]
            
            # 표시용 DataFrame 생성 (현재 페이지만)
            display_df = current_page_files.copy()
            display_df['상태'] = display_df['processed'].apply(lambda x: '✅ 처리완료' if x else '⏳ 미처리')
            display_df['청크수'] = display_df['chunks_count'].astype(int)
            
            # 필요한 컬럼만 선택하고 컬럼명 한국어로 변경
            display_columns = {
                'filename': '파일명',
                's3_key': 'S3 키',
                'upload_date': '업로드일',
                '상태': '상태',
                '청크수': '청크수'
            }
            
            # 깔끔한 표로 표시 (현재 페이지만)
            display_table = display_df[list(display_columns.keys())].rename(columns=display_columns)
            st.dataframe(display_table, use_container_width=True, hide_index=True)
            
            # 파일별 관리 버튼들 (현재 페이지만)
            st.subheader("🗑️ 파일 관리")
            
            for page_idx, (idx, row) in enumerate(current_page_files.iterrows()):
                # 고유한 키 생성 (페이지 + 인덱스)
                unique_key = f"page_{current_page}_item_{page_idx}"
                
                col1, col2, col3 = st.columns([4, 2, 1])
                
                with col1:
                    status_icon = "✅" if row['processed'] else "⏳"
                    st.write(f"{status_icon} **{row['filename']}**")
                
                with col2:
                    if row['processed']:
                        st.success(f"{row['chunks_count']}개 청크")
                    else:
                        st.warning("미처리")
                
                with col3:
                    # 삭제 확인 상태
                    delete_key = f"delete_confirm_{unique_key}"
                    if delete_key not in st.session_state:
                        st.session_state[delete_key] = False
                    
                    if not st.session_state[delete_key]:
                        if st.button("🗑️", key=f"delete_btn_{unique_key}", help="파일 삭제"):
                            st.session_state[delete_key] = True
                            st.rerun()
                    else:
                        # 삭제 확인 모드
                        subcol1, subcol2 = st.columns(2)
                        with subcol1:
                            if st.button("✅", key=f"confirm_{unique_key}", use_container_width=True, type="primary", help="삭제 확인"):
                                with st.spinner("삭제 중..."):
                                    if delete_file_from_s3_and_db(engine, s3_client, S3_BUCKET_NAME, row['id']):
                                        st.success("✅ 파일 삭제 완료!")
                                        if delete_key in st.session_state:
                                            del st.session_state[delete_key]
                                        st.rerun()
                                    else:
                                        st.error("삭제 실패")
                        with subcol2:
                            if st.button("❌", key=f"cancel_{unique_key}", use_container_width=True, help="삭제 취소"):
                                st.session_state[delete_key] = False
                                st.rerun()
                
                st.divider()
                # --- IndentationError 발생 지점 수정:
                # 이 로직은 col3가 끝난 후, 하지만 for 루프가 끝나기 전에 와야 합니다.
                # 그러나 기존 코드를 보면 이 로직이 중복된 것으로 보입니다.
                # 원본 코드의 의도를 살리기 위해 1349 라인 주변의 중복되는 삭제 확인 로직을 삭제합니다.
                # 원본 코드의 1300 라인부터 1345 라인까지 이미 삭제 로직이 제대로 구현되어 있습니다.
                # 이 부분(1349 라인~)은 중복/잘못된 들여쓰기로 판단되므로,
                # 오류 방지를 위해 원본 코드의 1349 라인 이후의 삭제 확인 로직을 주석 처리하거나 제거합니다.
                # 다만, 요청에 따라 IndentationError만 수정한다면 아래와 같이 들여쓰기를 조정해야 합니다.
                
                # 원본 코드의 IndentationError 발생 부분을 다음과 같이 수정합니다:
                # (1349 라인으로 추정되는 부분의 들여쓰기를 3단계로 수정하여 for 루프 안에 위치)
                if st.session_state.get(delete_key, False):
                    st.warning("정말 삭제하시겠습니까? (중복 로직)")
                    
                    col_yes, col_no = st.columns(2)
                    with col_yes:
                        if st.button("✅", key=f"delete_yes_{idx}", help="삭제 확인"):
                            with st.spinner("삭제 중..."):
                                # 이 로직은 1300-1345 라인에서 이미 처리되었으므로, 실제로는 도달하면 안 됩니다.
                                st.error("이미 위에 있는 버튼으로 처리되었어야 합니다. 코드를 정리해주세요.")
                                if delete_key in st.session_state:
                                     del st.session_state[delete_key]
                                st.rerun()
                    
                    with col_no:
                        if st.button("❌", key=f"delete_no_{idx}", help="삭제 취소"):
                            # 삭제 확인 상태 해제
                            if delete_key in st.session_state:
                                del st.session_state[delete_key]
                            st.rerun()
                
                # --- 수정 끝
                
                st.divider()
        else:
            st.info(f"**{selected_school}**에 업로드된 파일이 없습니다.")
        
        # 수동으로 S3 키 입력하여 처리
        st.subheader("🔧 수동 S3 파일 처리")
        st.info("S3에 직접 업로드된 파일이나 특정 경로의 파일을 처리할 수 있습니다.")
        st.caption("💡 팁: 위 표에서 S3 키를 복사해서 붙여넣으면 됩니다. `s3://` 형식도 자동으로 처리됩니다.")
        
        col1, col2 = st.columns([3, 1])
        with col1:
            manual_s3_key = st.text_input(
                "S3 키를 입력하세요:", 
                placeholder="예: documents/2024/01/15/file.pdf 또는 s3://bucket/path/file.pdf",
                key="manual_s3_key"
            )
        
        with col2:
            st.write("")  # 공간 조정
            st.write("")  # 공간 조정
            if st.button("📝 처리", disabled=not manual_s3_key):
                with st.spinner("처리 중..."):
                    # S3 URI에서 순수한 키만 추출
                    clean_s3_key = manual_s3_key
                    if clean_s3_key.startswith(f"s3://{S3_BUCKET_NAME}/"):
                        clean_s3_key = clean_s3_key.replace(f"s3://{S3_BUCKET_NAME}/", "")
                    elif clean_s3_key.startswith("s3://"):
                        # 다른 버킷 URI인 경우 버킷명도 제거
                        clean_s3_key = "/".join(clean_s3_key.split("/")[3:])
                    
                    chunks = process_pdf_from_s3(
                        s3_client, S3_BUCKET_NAME, clean_s3_key, 
                        vectorstore, embeddings, engine
                    )
                    if chunks > 0:
                        st.success(f"✅ {chunks}개 청크 처리 완료!")
                        st.rerun()
                    else:
                        st.error("처리에 실패했습니다. S3 키를 확인해주세요.")
    
    # 탭 4: RSS 피드
    with tab4:
        st.header("🔗 RSS 피드 관리")
        st.info(f"📚 **{selected_school}**의 RSS 피드를 관리합니다.")
        
        # RSS 추가 섹션
        st.subheader("🆕 새 RSS 피드 추가")
        col1, col2 = st.columns([4, 1])
        
        with col1:
            # URL 입력 필드 초기화를 위한 세션 상태 관리
            if 'rss_url_input' not in st.session_state:
                st.session_state.rss_url_input = ""
            
            rss_url = st.text_input(
                "RSS 피드 URL을 입력하세요:",
                placeholder="https://example.com/rss",
                key="new_rss_url",
                value=st.session_state.rss_url_input
            )
        
        with col2:
            st.write("")  # 공간 조정
            st.write("")  # 공간 조정
            if st.button("➕ 추가", disabled=not rss_url):
                with st.spinner("RSS 피드를 추가하고 있습니다..."):
                    rss_feed_id = add_rss_feed(engine, school_id, rss_url)
                    if rss_feed_id:
                        st.success("✅ RSS 피드가 추가되었습니다!")
                        # URL 입력 필드 초기화
                        st.session_state.rss_url_input = ""
                        st.rerun()
                    else:
                        st.warning("이미 등록된 RSS 피드이거나 추가에 실패했습니다.")
        
        st.divider()
        
        # 등록된 RSS 피드 목록
        st.subheader("📡 등록된 RSS 피드 목록")
        rss_feeds = get_rss_feeds(engine, school_id)
        
        if not rss_feeds.empty:
            # 통계 표시
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("등록된 피드", len(rss_feeds))
            with col2:
                active_feeds = len(rss_feeds[rss_feeds['status'] == 'active'])
                st.metric("활성 피드", active_feeds)
            with col3:
                total_items = rss_feeds['processed_count'].sum()
                st.metric("처리된 항목", int(total_items))
            
            st.write("")
            
            # RSS 피드 데이터프레임 표시용 데이터 준비
            display_df = rss_feeds.copy()
            
            # 표시용 컬럼 정리
            display_df['피드명'] = display_df['title'].fillna('제목 없음')
            display_df['RSS URL'] = display_df['rss_url'].apply(
                lambda x: f"{x[:60]}..." if len(x) > 60 else x
            )
            display_df['상태'] = display_df['status'].apply(
                lambda x: "✅ 활성" if x == 'active' else "⏸️ 비활성"
            )
            display_df['처리된 항목'] = display_df['processed_count'].astype(int)
            display_df['마지막 처리'] = display_df['last_processed'].apply(
                lambda x: x.strftime('%m-%d %H:%M') if pd.notnull(x) else '미처리'
            )
            display_df['등록일'] = display_df['created_at'].apply(
                lambda x: x.strftime('%m-%d') if pd.notnull(x) else 'N/A'
            )
            
            # 표시할 컬럼만 선택
            show_columns = ['피드명', 'RSS URL', '상태', '처리된 항목', '마지막 처리', '등록일']
            
            # 깔끔한 데이터프레임 표시
            st.dataframe(
                display_df[show_columns], 
                use_container_width=True,
                hide_index=True
            )
            
            st.write("---")
            
            # 각 RSS 피드별 액션 및 미리보기
            st.subheader("🔧 RSS 피드 관리")
            
            for idx, row in rss_feeds.iterrows():
                with st.container():
                    # RSS 기본 정보와 버튼들
                    col1, col2, col3, col4 = st.columns([4, 1.5, 1.5, 1])
                    
                    with col1:
                        title = row['title'] if row['title'] else "제목 없음"
                        status_icon = "✅" if row['status'] == 'active' else "⏸️"
                        st.write(f"{status_icon} **{title}**")
                        st.caption(f"🔗 {row['rss_url'][:70]}...")
                        st.caption(f"📊 {int(row['processed_count'])}개 항목")
                    
                    with col2:
                        # 미리보기 버튼
                        preview_key = f"preview_{row['id']}"
                        preview_text = "📋 미리보기 닫기" if st.session_state.get(preview_key, False) else "📋 미리보기"
                        
                        if st.button(preview_text, key=f"preview_btn_{row['id']}", use_container_width=True):
                            if preview_key not in st.session_state:
                                st.session_state[preview_key] = False
                            st.session_state[preview_key] = not st.session_state[preview_key]
                            st.rerun()
                    
                    with col3:
                        # 처리 버튼
                        if st.button(f"🔄 처리", key=f"process_{row['id']}", use_container_width=True):
                            with st.spinner("처리 중..."):
                                chunks = process_rss_feed(row['rss_url'], vectorstore, engine, embeddings, school_id)
                                if chunks > 0:
                                    st.success(f"✅ {chunks}개 항목 처리 완료!")
                                    st.rerun()
                                else:
                                    st.info("새로운 항목이 없습니다.")
                    
                    with col4:
                        # 삭제 버튼
                        delete_key = f"delete_rss_{row['id']}"
                        if delete_key not in st.session_state:
                            st.session_state[delete_key] = False
                        
                        if not st.session_state[delete_key]:
                            if st.button("🗑️", key=f"rss_delete_btn_{row['id']}", use_container_width=True, type="secondary", help="RSS 피드 삭제"):
                                st.session_state[delete_key] = True
                                st.rerun()
                        else:
                            # 삭제 확인 모드 - 같은 컬럼에서 확인/취소 버튼
                            subcol1, subcol2 = st.columns(2)
                            with subcol1:
                                if st.button("✅", key=f"rss_confirm_{row['id']}", use_container_width=True, type="primary", help="삭제 확인"):
                                    with st.spinner("삭제 중..."):
                                        if delete_rss_feed(engine, row['id']):
                                            st.success("✅ 삭제 완료!")
                                            # URL 입력 필드도 초기화
                                            st.session_state.rss_url_input = ""
                                            # 관련 세션 상태 정리
                                            if delete_key in st.session_state:
                                                del st.session_state[delete_key]
                                            preview_key = f"preview_{row['id']}"
                                            if preview_key in st.session_state:
                                                del st.session_state[preview_key]
                                            st.rerun()
                                        else:
                                            st.error("삭제 실패")
                            with subcol2:
                                if st.button("❌", key=f"rss_cancel_{row['id']}", use_container_width=True, help="삭제 취소"):
                                    st.session_state[delete_key] = False
                                    st.rerun()
                    
                    # RSS 미리보기 (해당 피드 버튼을 눌렀을 때만 표시)
                    preview_key = f"preview_{row['id']}"
                    if st.session_state.get(preview_key, False):
                        with st.expander("📋 RSS 피드 미리보기", expanded=True):
                            try:
                                feed = feedparser.parse(row['rss_url'])
                                if feed.entries:
                                    col1, col2 = st.columns(2)
                                    with col1:
                                        st.metric("피드 제목", feed.feed.get('title', 'N/A'))
                                    with col2:
                                        st.metric("총 항목 수", len(feed.entries))
                                    
                                    # 최신 5개 항목 미리보기
                                    st.write("**📰 최신 항목들:**")
                                    for i, entry in enumerate(feed.entries[:5]):
                                        with st.container():
                                            st.write(f"**{i+1}. {entry.get('title', 'N/A')}**")
                                            st.write(f"🔗 {entry.get('link', 'N/A')}")
                                            st.write(f"📅 {entry.get('published', 'N/A')}")
                                            summary = entry.get('summary', entry.get('description', ''))
                                            if summary:
                                                st.write(f"📄 {summary[:200]}...")
                                            if i < 4:  # 마지막 항목이 아니면 구분선
                                                st.write("---")
                                else:
                                    st.warning("RSS 피드에서 항목을 찾을 수 없습니다.")
                            except Exception as e:
                                st.error(f"RSS 피드 미리보기 실패: {str(e)}")
                    
                    st.divider()
            
        else:
            st.info("등록된 RSS 피드가 없습니다. 위에서 새 RSS 피드를 추가해보세요!")
    
    # 탭 5: 파일 관리
    with tab5:
        st.header(f"📊 파일 관리 - {selected_school}")
        
        # 파일 메타데이터 조회 (school_id 필터링 적용)
        file_metadata = get_file_metadata(engine, school_id)
        
        if not file_metadata.empty:
            st.subheader("업로드된 파일 목록")
            st.dataframe(file_metadata)
            
            # 통계
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("총 파일 수", len(file_metadata))
            with col2:
                processed_count = len(file_metadata[file_metadata['processed'] == True])
                st.metric("처리된 파일", processed_count)
            with col3:
                unprocessed_count = len(file_metadata[file_metadata['processed'] == False])
                st.metric("미처리 파일", unprocessed_count)
        else:
            st.info(f"**{selected_school}**에 업로드된 파일이 없습니다.")
        
        # 문서 청크 통계 (school_id 필터링 적용)
        st.subheader("문서 콘텐츠 통계")
        try:
            with engine.connect() as conn:
                # school_id로 필터링된 청크 수
                result = conn.execute(text("""
                    SELECT COUNT(dc.*) 
                    FROM document_chunks dc 
                    JOIN documents d ON dc.document_id = d.id 
                    WHERE d.school_id = :school_id
                """), {"school_id": school_id}).fetchone()
                chunks_count = result[0] if result else 0
                st.metric("문서 청크 수", chunks_count)
                
                # school_id로 필터링된 처리된 문서 수
                result = conn.execute(text("""
                    SELECT COUNT(DISTINCT dc.document_id) 
                    FROM document_chunks dc 
                    JOIN documents d ON dc.document_id = d.id 
                    WHERE d.school_id = :school_id
                """), {"school_id": school_id}).fetchone()
                docs_count = result[0] if result else 0
                st.metric("처리된 문서 수", docs_count)
                
                # 카테고리별 통계 (school_id 필터링 적용)
                result = conn.execute(text("""
                    SELECT d.category, 
                            COUNT(d.id) as total_docs,
                            SUM(CASE WHEN d.processed THEN 1 ELSE 0 END) as processed_docs,
                            SUM(COALESCE(d.chunks_count, 0)) as total_chunks
                    FROM documents d
                    WHERE d.school_id = :school_id
                    GROUP BY d.category
                    ORDER BY d.category
                """), {"school_id": school_id}).fetchall()
                
                if result:
                    st.subheader("카테고리별 상세 통계")
                    for row in result:
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.write(f"**{row[0]}**")
                        with col2:
                            st.metric("총 문서", row[1])
                        with col3:
                            st.metric("처리 완료", row[2])
                        with col4:
                            st.metric("청크 수", row[3])
                        
        except Exception as e:
            st.error(f"통계 조회 실패: {str(e)}")

if __name__ == "__main__":
    main()
