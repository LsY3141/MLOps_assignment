-- pgvector 확장 설치 (관리자 권한 필요)
CREATE EXTENSION IF NOT EXISTS vector;

-- 문서 메타데이터 테이블
CREATE TABLE IF NOT EXISTS document_metadata (
    id SERIAL PRIMARY KEY,
    filename VARCHAR(255) NOT NULL,
    s3_key VARCHAR(255) NOT NULL UNIQUE,
    upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    document_type VARCHAR(50) NOT NULL,
    processed BOOLEAN DEFAULT FALSE,
    chunks_count INTEGER DEFAULT 0,
    file_size INTEGER,
    description TEXT
);

-- RSS 피드 메타데이터 테이블
CREATE TABLE IF NOT EXISTS rss_feeds (
    id SERIAL PRIMARY KEY,
    rss_url VARCHAR(500) NOT NULL UNIQUE,
    title VARCHAR(255),
    description TEXT,
    last_processed TIMESTAMP,
    total_items INTEGER DEFAULT 0,
    active BOOLEAN DEFAULT TRUE,
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 문서 청크 테이블 (pgvector가 없는 경우 대체용)
CREATE TABLE IF NOT EXISTS document_chunks (
    id SERIAL PRIMARY KEY,
    s3_key VARCHAR(255) NOT NULL,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    metadata JSONB,
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(s3_key, chunk_index)
);

-- RSS 청크 테이블 (pgvector가 없는 경우 대체용) 
CREATE TABLE IF NOT EXISTS rss_chunks (
    id SERIAL PRIMARY KEY,
    rss_url VARCHAR(500) NOT NULL,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    metadata JSONB,
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 전문 검색을 위한 인덱스 생성
CREATE INDEX IF NOT EXISTS idx_document_chunks_content_fts 
ON document_chunks USING gin(to_tsvector('korean', content));

CREATE INDEX IF NOT EXISTS idx_rss_chunks_content_fts 
ON rss_chunks USING gin(to_tsvector('korean', content));

-- 일반 인덱스들
CREATE INDEX IF NOT EXISTS idx_document_metadata_s3_key ON document_metadata(s3_key);
CREATE INDEX IF NOT EXISTS idx_document_metadata_processed ON document_metadata(processed);
CREATE INDEX IF NOT EXISTS idx_rss_feeds_url ON rss_feeds(rss_url);
CREATE INDEX IF NOT EXISTS idx_document_chunks_s3_key ON document_chunks(s3_key);
CREATE INDEX IF NOT EXISTS idx_rss_chunks_url ON rss_chunks(rss_url);

-- pgvector가 있는 경우 langchain이 자동으로 생성할 테이블들:
-- langchain_pg_collection
-- langchain_pg_embedding

COMMENT ON TABLE document_metadata IS '업로드된 문서들의 메타데이터를 저장하는 테이블';
COMMENT ON TABLE rss_feeds IS 'RSS 피드 정보를 관리하는 테이블';
COMMENT ON TABLE document_chunks IS '문서 청크 저장 테이블 (pgvector 대체용)';
COMMENT ON TABLE rss_chunks IS 'RSS 청크 저장 테이블 (pgvector 대체용)';

