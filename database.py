import streamlit as st
import pandas as pd
import feedparser
import re
from sqlalchemy import create_engine, text
from langchain_community.vectorstores import PGVector

# 분리된 설정 파일에서 설정값 가져오기
from config import settings

# --- 초기화 함수 ---

@st.cache_resource
def init_postgresql_vectorstore():
    """PostgreSQL을 벡터 스토어로 초기화합니다."""
    try:
        engine = create_engine(settings.DATABASE_URL)
        
        # 연결 테스트 및 필요한 컬럼 추가
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            try:
                conn.execute(text("ALTER TABLE documents ADD COLUMN IF NOT EXISTS processed BOOLEAN DEFAULT FALSE"))
                conn.execute(text("ALTER TABLE documents ADD COLUMN IF NOT EXISTS chunks_count INTEGER DEFAULT 0"))
                conn.commit()
            except Exception:
                # 컬럼이 이미 있거나 권한 문제면 무시
                pass
        
        return engine
    except Exception as e:
        st.error(f"PostgreSQL 초기화 실패: {str(e)}")
        return None

@st.cache_resource 
def init_pgvector(_embeddings, _engine):
    """PGVector 벡터 스토어를 초기화합니다."""
    if not _embeddings:
        st.warning("임베딩 모델이 없어 벡터 검색을 사용할 수 없습니다.")
        return None
    
    try:
        vectorstore = PGVector(
            connection_string=settings.DATABASE_URL,
            embedding_function=_embeddings,
            collection_name="university_docs"
        )
        return vectorstore
    except Exception as e:
        st.error(f"PGVector 초기화 실패: {str(e)}")
        st.warning("벡터 검색 대신 텍스트 검색을 사용합니다.")
        return None

# --- 데이터 조회 함수 ---

def get_schools_list(engine):
    """학교 목록을 조회합니다."""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT id, name, code FROM schools ORDER BY name"))
            schools = result.fetchall()
            return {school[1]: school[0] for school in schools}  # {name: id} 형태
    except Exception as e:
        st.error(f"학교 목록 조회 실패: {str(e)}")
        return {"연성대학교": 1}  # 기본값

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
                "total_chunks": int(stats[2] or 0)
            }
    except Exception as e:
        st.error(f"통계 조회 실패: {str(e)}")
        return {"total_documents": 0, "processed_documents": 0, "total_chunks": 0}

def get_school_code_by_id(engine, school_id):
    """school_id로 학교 코드를 조회합니다."""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT code FROM schools WHERE id = :school_id"), 
                                 {"school_id": school_id})
            school = result.fetchone()
            return school[0] if school else "UNK"
    except Exception:
        return "UNK"

def get_file_metadata(engine, school_id):
    """documents 테이블에서 특정 학교의 파일 메타데이터를 조회합니다."""
    try:
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
        return df
    except Exception as e:
        st.error(f"메타데이터 조회 실패: {str(e)}")
        return pd.DataFrame()

def get_rss_feeds(engine, school_id):
    """특정 학교의 RSS 피드 목록을 조회합니다."""
    try:
        df = pd.read_sql("""
            SELECT rf.id, rf.url as rss_url, rf.title, rf.last_processed,
                    rf.processed_count, rf.status, rf.created_at
            FROM rss_feeds rf
            WHERE rf.school_id = %(school_id)s
            ORDER BY rf.created_at DESC
        """, engine, params={"school_id": school_id})
        return df
    except Exception as e:
        st.error(f"RSS 피드 조회 실패: {str(e)}")
        return pd.DataFrame()

# --- 데이터 수정/삭제 함수 ---

def save_file_metadata(engine, filename, s3_key, doc_type, school_id):
    """파일 메타데이터를 documents 테이블에 저장합니다."""
    try:
        with engine.connect() as conn:
            source_url = s3_key if s3_key.startswith('s3://') else f"s3://{settings.S3_BUCKET_NAME}/{s3_key}"
            
            existing_doc = conn.execute(text("""
                SELECT id FROM documents 
                WHERE source_url = :source_url OR (file_name = :filename AND school_id = :school_id)
            """), {"source_url": source_url, "filename": filename, "school_id": school_id}).fetchone()
            
            if not existing_doc:
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

def add_rss_feed(engine, school_id, rss_url):
    """새 RSS 피드를 rss_feeds 테이블에 추가합니다."""
    try:
        feed = feedparser.parse(rss_url)
        feed_title = feed.feed.get('title', rss_url)
        
        with engine.connect() as conn:
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
                return new_feed[0]
            else:
                existing = conn.execute(text("""
                    SELECT id FROM rss_feeds 
                    WHERE school_id = :school_id AND url = :url
                """), {"school_id": school_id, "url": rss_url}).fetchone()
                return existing[0] if existing else None
                
    except Exception as e:
        st.error(f"RSS 피드 추가 실패: {str(e)}")
        return None

def delete_rss_feed(engine, rss_feed_id):
    """RSS 피드와 관련 데이터를 삭제합니다."""
    try:
        with engine.connect() as conn:
            rss_info = conn.execute(text("SELECT url, school_id FROM rss_feeds WHERE id = :rss_id"), {"rss_id": rss_feed_id}).fetchone()
            if not rss_info: return False
            
            rss_url, school_id = rss_info
            
            docs = conn.execute(text("SELECT id FROM documents WHERE source_url = :url AND category = 'rss' AND school_id = :school_id"), {"url": rss_url, "school_id": school_id}).fetchall()
            
            for doc in docs:
                conn.execute(text("DELETE FROM document_chunks WHERE document_id = :doc_id"), {"doc_id": doc[0]})
            
            conn.execute(text("DELETE FROM documents WHERE source_url = :url AND category = 'rss' AND school_id = :school_id"), {"url": rss_url, "school_id": school_id})
            
            conn.execute(text("DELETE FROM rss_feeds WHERE id = :rss_id"), {"rss_id": rss_feed_id})
            
            conn.commit()
            return True
    except Exception as e:
        st.error(f"RSS 피드 삭제 실패: {str(e)}")
        return False

def delete_document_from_db(engine, document_id):
    """문서와 관련 청크를 DB에서 완전히 삭제합니다."""
    try:
        with engine.connect() as conn:
            conn.execute(text("DELETE FROM document_chunks WHERE document_id = :document_id"), {"document_id": document_id})
            conn.execute(text("DELETE FROM documents WHERE id = :document_id"), {"document_id": document_id})
            conn.commit()
            return True
    except Exception as e:
        st.error(f"문서 삭제 실패: {str(e)}")
        return False

# --- 부서 검색 관련 함수 ---

def find_relevant_department(engine, query, school_id):
    """질문 키워드를 분석하여 가장 관련성 높은 부서를 찾습니다."""
    try:
        with engine.connect() as conn:
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
            
            if not result: return None
                
            query_processed = re.sub(r'[^\w가-힣]', ' ', query.lower()).strip()
            query_words = query_processed.split()
            
            department_scores = {}
            department_info = {}
            
            for row in result:
                dept_id, dept_name, keyword, weight = row[0], row[1], row[4], row[5] or 1
                
                if dept_id not in department_info:
                    department_info[dept_id] = {
                        'name': dept_name, 'description': row[2], 'main_phone': row[3],
                        'staff_name': row[6], 'staff_position': row[7], 'staff_phone': row[8],
                        'staff_email': row[9], 'staff_responsibilities': row[10]
                    }
                
                if keyword:
                    department_scores.setdefault(dept_id, 0)
                    keyword_lower = keyword.lower()
                    if keyword_lower in query_processed:
                        department_scores[dept_id] += weight * 3
                    elif any(word in keyword_lower or keyword_lower in word for word in query_words):
                        department_scores[dept_id] += weight * 2
                    elif any(is_similar_keyword(word, keyword_lower) for word in query_words):
                        department_scores[dept_id] += weight
            
            if department_scores:
                best_dept_id, best_score = max(department_scores.items(), key=lambda x: x[1])
                if best_score > 0:
                    return department_info[best_dept_id]
            
        return None
    except Exception as e:
        st.error(f"부서 검색 실패: {str(e)}")
        return None

def is_similar_keyword(word, keyword):
    """두 키워드가 유사한지 판단합니다."""
    similar_pairs = [
        (['등록금', '학비', '납부금'], ['등록금', '납부']), (['수강신청', '수강', '강의신청'], ['수강신청', '수업관리']),
        (['성적', '학점', '점수'], ['성적']), (['졸업', '졸업요건', '학위'], ['졸업']),
        (['휴학', '휴학신청'], ['휴학']), (['복학', '복학신청'], ['복학']),
        (['장학금', '장학', '지원금'], ['장학금']), (['취업', '취업지원', '일자리'], ['취업', '진로']),
        (['입학', '입시', '신입생'], ['입학', '입시', '모집']), (['실습', '현장실습', '인턴십'], ['현장실습', '실험실습']),
        (['상담', '심리상담', '학생상담'], ['심리상담', '학생상담']), (['시설', '건물', '공사'], ['시설', '공사']),
        (['인사', '인사관리', '직원'], ['인사']), (['예산', '회계', '재정'], ['예산', '회계'])
    ]
    for word_group, keyword_group in similar_pairs:
        if word in word_group and keyword in keyword_group:
            return True
    return False
