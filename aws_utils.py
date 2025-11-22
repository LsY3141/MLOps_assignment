import boto3
import streamlit as st
import tempfile
import os
import feedparser
from langchain_aws import BedrockEmbeddings
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import CharacterTextSplitter
from sqlalchemy import text

from config import settings

# BedrockEmbeddings 클래스를 동적으로 import
try:
    from langchain_aws import BedrockEmbeddings
except ImportError:
    try:
        from langchain_community.embeddings import BedrockEmbeddings
    except ImportError:
        BedrockEmbeddings = None

# --- AWS 클라이언트 초기화 ---

@st.cache_resource
def init_aws_clients():
    """EC2 IAM 역할을 사용하여 AWS 클라이언트들을 초기화합니다."""
    try:
        bedrock_runtime_client = boto3.client("bedrock-runtime", region_name=settings.AWS_REGION)
        s3_client = boto3.client("s3", region_name=settings.AWS_REGION)
        
        embeddings = None
        if BedrockEmbeddings:
            try:
                embeddings = BedrockEmbeddings(
                    client=bedrock_runtime_client,
                    region_name=settings.AWS_REGION,
                    model_id="cohere.embed-v4:0" # cohere.embed-multilingual-v3.0
                )
            except Exception as e:
                st.warning(f"임베딩 모델 초기화 실패: {str(e)}")
        else:
            st.warning("BedrockEmbeddings를 사용할 수 없어 임베딩 기능이 비활성화됩니다.")
        
        return bedrock_runtime_client, embeddings, s3_client
    except Exception as e:
        st.error(f"AWS 클라이언트 초기화 실패: {str(e)}")
        return None, None, None

# --- S3 관련 함수 ---

def upload_to_s3(file, s3_client, key):
    """파일을 S3에 업로드합니다."""
    try:
        s3_client.upload_fileobj(file, settings.S3_BUCKET_NAME, key)
        return True
    except Exception as e:
        st.error(f"S3 업로드 실패: {str(e)}")
        return False

def delete_file_from_s3(s3_client, s3_key):
    """S3에서 파일을 삭제합니다."""
    try:
        s3_client.delete_object(Bucket=settings.S3_BUCKET_NAME, Key=s3_key)
        return True
    except Exception as e:
        st.error(f"S3 파일 삭제 실패: {str(e)}")
        return False

# --- 데이터 처리 함수 ---

def process_pdf_from_s3(s3_client, key, engine, school_id, embeddings=None):
    """S3의 PDF 파일을 처리하여 PostgreSQL DB에 저장합니다."""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            s3_client.download_fileobj(settings.S3_BUCKET_NAME, key, tmp_file)
            tmp_path = tmp_file.name
        
        pdf_loader = PyPDFLoader(tmp_path)
        splitter = CharacterTextSplitter.from_tiktoken_encoder(
            separator="\n", chunk_size=800, chunk_overlap=100
        )
        documents = pdf_loader.load_and_split(text_splitter=splitter)
        
        with engine.connect() as conn:
            source_url = f"s3://{settings.S3_BUCKET_NAME}/{key}"
            file_name = key.split('/')[-1]

            existing_doc = conn.execute(text("""
                SELECT id FROM documents WHERE source_url = :source_url OR (file_name = :file_name AND school_id = :school_id)
            """), {"source_url": source_url, "file_name": file_name, "school_id": school_id}).fetchone()

            if existing_doc:
                document_id = existing_doc[0]
                conn.execute(text("UPDATE documents SET processed = TRUE, chunks_count = :chunks_count WHERE id = :id"),
                             {"chunks_count": len(documents), "id": document_id})
            else:
                result = conn.execute(text("""
                    INSERT INTO documents (school_id, file_name, source_url, category, processed, chunks_count)
                    VALUES (:school_id, :file_name, :source_url, 'pdf', TRUE, :chunks_count) RETURNING id
                """), {"school_id": school_id, "file_name": file_name, "source_url": source_url, "chunks_count": len(documents)}).fetchone()[0]
                document_id = result

            conn.execute(text("DELETE FROM document_chunks WHERE document_id = :document_id"), {"document_id": document_id})

            for doc in documents:
                embedding_vector = embeddings.embed_query(doc.page_content) if embeddings else None
                conn.execute(text("""
                    INSERT INTO document_chunks (document_id, chunk_text, embedding)
                    VALUES (:document_id, :chunk_text, :embedding)
                """), {"document_id": document_id, "chunk_text": doc.page_content, "embedding": embedding_vector})
            
            conn.commit()
        
        os.unlink(tmp_path)
        return len(documents)
    except Exception as e:
        st.error(f"PDF 처리 실패: {str(e)}")
        return 0

def process_rss_feed(engine, rss_url, school_id, embeddings=None):
    """RSS 피드를 처리하여 DB에 저장합니다."""
    try:
        feed = feedparser.parse(rss_url)
        chunks_processed = 0
        skipped_duplicates = 0
        
        with engine.connect() as conn:
            feed_title = feed.feed.get('title', rss_url)
            rss_feed_result = conn.execute(text("""
                INSERT INTO rss_feeds (school_id, url, title, status)
                VALUES (:school_id, :url, :title, 'active')
                ON CONFLICT (school_id, url) DO UPDATE SET title = EXCLUDED.title, last_processed = NOW()
                RETURNING id
            """),
            {"school_id": school_id, "url": rss_url, "title": feed_title}).fetchone()
            
            rss_feed_id = rss_feed_result[0]
            
            existing_doc = conn.execute(text("""
                SELECT id FROM documents WHERE source_url = :rss_url AND category = 'rss' AND school_id = :school_id
            """),
            {"rss_url": rss_url, "school_id": school_id}).fetchone()
            
            document_id = existing_doc[0] if existing_doc else conn.execute(text("""
                INSERT INTO documents (school_id, source_url, category, processed, chunks_count)
                VALUES (:school_id, :rss_url, 'rss', FALSE, 0) RETURNING id
            """),
            {"school_id": school_id, "rss_url": rss_url}).fetchone()[0]
            
            existing_contents = conn.execute(text("SELECT chunk_text FROM document_chunks WHERE document_id = :id"), {"id": document_id}).fetchall()
            existing_titles = {line.replace('제목:', '').strip() for row in existing_contents for line in row[0].split('\n') if line.strip().startswith('제목:')}
            existing_links = {line.replace('링크:', '').strip() for row in existing_contents for line in row[0].split('\n') if line.strip().startswith('링크:')}

            for entry in feed.entries:
                entry_title = entry.get('title', '').strip()
                entry_link = entry.get('link', '').strip()

                if entry_title in existing_titles or entry_link in existing_links:
                    skipped_duplicates += 1
                    continue
                
                content = f"제목: {entry_title}\n내용: {entry.get('summary', '')}\n링크: {entry_link}\n발행일: {entry.get('published', '')}"
                
                splitter = CharacterTextSplitter.from_tiktoken_encoder(separator="\n", chunk_size=800, chunk_overlap=100)
                chunks = splitter.split_text(content)
                
                for chunk in chunks:
                    embedding_vector = embeddings.embed_query(chunk) if embeddings else None
                    conn.execute(text("""
                        INSERT INTO document_chunks (document_id, chunk_text, embedding)
                        VALUES (:doc_id, :chunk, :vec)
                    """),
                    {"doc_id": document_id, "chunk": chunk, "vec": embedding_vector})
                    chunks_processed += 1
                
                existing_titles.add(entry_title)
                existing_links.add(entry_link)

            total_chunks = conn.execute(text("SELECT COUNT(*) FROM document_chunks WHERE document_id = :id"), {"id": document_id}).fetchone()[0]
            conn.execute(text("UPDATE documents SET processed = TRUE, chunks_count = :count WHERE id = :id"), {"count": total_chunks, "id": document_id})
            conn.execute(text("UPDATE rss_feeds SET last_processed = NOW(), processed_count = :count WHERE id = :id"), {"count": total_chunks, "id": rss_feed_id})
            conn.commit()
        
        if skipped_duplicates > 0:
            st.info(f"📊 처리 결과: 신규 {chunks_processed}개 청크 추가, 중복 {skipped_duplicates}개 항목 스킵")
        
        return chunks_processed
    except Exception as e:
        st.error(f"RSS 피드 처리 실패: {str(e)}")
        return 0
