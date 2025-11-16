"""
S3 이벤트 트리거 Lambda 함수
S3에 PDF 파일이 업로드되면 자동으로 실행되어 벡터화 처리

트리거 조건:
- 이벤트: s3:ObjectCreated:Put, s3:ObjectCreated:Post
- 접미사: .pdf

환경 변수:
- DB_HOST: RDS 호스트
- DB_NAME: 데이터베이스 이름
- DB_USER: DB 사용자명
- DB_PASSWORD: DB 비밀번호
- AWS_REGION: AWS 리전
- API_ENDPOINT: FastAPI 서버 엔드포인트 (예: http://ec2-ip:8000)
- DEFAULT_SCHOOL_ID: 기본 학교 ID
"""

import json
import os
import urllib.parse
import boto3
from io import BytesIO
import psycopg2
from PyPDF2 import PdfReader
import logging

# 로깅 설정
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# AWS 클라이언트
s3_client = boto3.client('s3')
bedrock_client = boto3.client('bedrock-runtime', region_name=os.getenv('AWS_REGION', 'us-west-1'))


def extract_metadata_from_s3_path(s3_key: str) -> dict:
    """
    S3 경로에서 메타데이터를 추출합니다.

    예상 경로 구조: documents/{school_id}/{category}/{filename}
    또는: documents/{filename}

    Args:
        s3_key: S3 객체 키

    Returns:
        메타데이터 딕셔너리
    """
    parts = s3_key.split('/')

    metadata = {
        'school_id': int(os.getenv('DEFAULT_SCHOOL_ID', 1)),
        'category': 'general',
        'department': None
    }

    # 경로 구조 파싱
    if len(parts) >= 4 and parts[0] == 'documents':
        try:
            metadata['school_id'] = int(parts[1])
            metadata['category'] = parts[2]
        except (ValueError, IndexError):
            pass

    # 파일명에서 카테고리 추론 (선택적)
    filename = parts[-1].lower()
    if 'scholarship' in filename or '장학' in filename:
        metadata['category'] = 'scholarship'
    elif 'academic' in filename or '학사' in filename:
        metadata['category'] = 'academic'
    elif 'facility' in filename or '시설' in filename:
        metadata['category'] = 'facilities'
    elif 'career' in filename or '진로' in filename or '취업' in filename:
        metadata['category'] = 'career'

    return metadata


def extract_text_from_pdf(bucket: str, key: str) -> str:
    """
    S3에서 PDF를 다운로드하고 텍스트를 추출합니다.

    Args:
        bucket: S3 버킷 이름
        key: S3 객체 키

    Returns:
        추출된 텍스트
    """
    logger.info(f"📥 Downloading PDF from s3://{bucket}/{key}")

    # S3에서 PDF 다운로드
    response = s3_client.get_object(Bucket=bucket, Key=key)
    pdf_stream = BytesIO(response['Body'].read())

    # PDF 텍스트 추출
    reader = PdfReader(pdf_stream)
    text = ""

    for i, page in enumerate(reader.pages):
        page_text = page.extract_text() or ""
        text += f"[페이지 {i+1}]\n{page_text}\n\n"

    logger.info(f"✅ Extracted {len(text)} characters from {len(reader.pages)} pages")
    return text.strip()


def chunk_text(text: str, chunk_size: int = 1000, chunk_overlap: int = 200) -> list:
    """
    텍스트를 청크로 분할합니다.

    Args:
        text: 분할할 텍스트
        chunk_size: 청크 크기
        chunk_overlap: 청크 간 중복

    Returns:
        청크 리스트
    """
    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]

        if len(chunk.strip()) > 50:  # 최소 50자
            chunks.append(chunk.strip())

        start += (chunk_size - chunk_overlap)

    logger.info(f"✂️  Created {len(chunks)} chunks")
    return chunks


def generate_embedding(text: str) -> list:
    """
    Bedrock Titan을 사용하여 임베딩을 생성합니다.

    Args:
        text: 임베딩할 텍스트

    Returns:
        임베딩 벡터 (1536차원) 또는 None
    """
    try:
        # 텍스트 길이 제한
        if len(text) > 30000:
            text = text[:30000] + "..."

        body = json.dumps({"inputText": text})
        response = bedrock_client.invoke_model(
            body=body,
            modelId="amazon.titan-embed-text-v1",
            accept="application/json",
            contentType="application/json"
        )

        response_body = json.loads(response.get("body").read())
        embedding = response_body.get("embedding")

        return embedding

    except Exception as e:
        logger.error(f"❌ Embedding generation failed: {e}")
        return None


def save_to_database(
    bucket: str,
    key: str,
    text: str,
    chunks: list,
    metadata: dict
):
    """
    문서와 청크를 데이터베이스에 저장합니다.

    Args:
        bucket: S3 버킷
        key: S3 키
        text: 원본 텍스트
        chunks: 텍스트 청크 리스트
        metadata: 메타데이터
    """
    # 데이터베이스 연결
    conn = psycopg2.connect(
        host=os.getenv('DB_HOST'),
        database=os.getenv('DB_NAME'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        port=5432
    )

    try:
        cur = conn.cursor()

        # S3 URL 생성
        s3_url = f"https://{bucket}.s3.{os.getenv('AWS_REGION', 'us-west-1')}.amazonaws.com/{key}"
        filename = key.split('/')[-1]

        # 1. Document 레코드 삽입
        cur.execute("""
            INSERT INTO documents (school_id, category, file_name, source_url, department, created_at)
            VALUES (%s, %s, %s, %s, %s, NOW())
            RETURNING id
        """, (
            metadata['school_id'],
            metadata['category'],
            filename,
            s3_url,
            metadata['department']
        ))

        document_id = cur.fetchone()[0]
        logger.info(f"💾 Document saved with ID: {document_id}")

        # 2. 각 청크에 대해 임베딩 생성 및 저장
        chunk_count = 0
        for i, chunk_text in enumerate(chunks):
            # 임베딩 생성
            embedding = generate_embedding(chunk_text)

            if embedding:
                # pgvector 형식으로 변환
                embedding_str = '[' + ','.join(map(str, embedding)) + ']'

                cur.execute("""
                    INSERT INTO document_chunks (document_id, chunk_text, embedding)
                    VALUES (%s, %s, %s::vector)
                """, (document_id, chunk_text, embedding_str))

                chunk_count += 1
            else:
                # 임베딩 없이 텍스트만 저장 (키워드 검색용)
                cur.execute("""
                    INSERT INTO document_chunks (document_id, chunk_text, embedding)
                    VALUES (%s, %s, NULL)
                """, (document_id, chunk_text))

                chunk_count += 1

        conn.commit()
        logger.info(f"✅ Saved {chunk_count} chunks to database")

    except Exception as e:
        conn.rollback()
        logger.error(f"❌ Database error: {e}")
        raise

    finally:
        cur.close()
        conn.close()


def lambda_handler(event, context):
    """
    Lambda 핸들러 함수
    S3 이벤트를 받아 PDF를 처리합니다.

    Args:
        event: S3 이벤트
        context: Lambda 컨텍스트

    Returns:
        처리 결과
    """
    logger.info("=" * 60)
    logger.info("🚀 S3 PDF 자동 벡터화 Lambda 시작")
    logger.info("=" * 60)

    try:
        # S3 이벤트에서 버킷과 키 추출
        record = event['Records'][0]
        bucket = record['s3']['bucket']['name']
        key = urllib.parse.unquote_plus(record['s3']['object']['key'], encoding='utf-8')

        logger.info(f"📂 Bucket: {bucket}")
        logger.info(f"📄 Key: {key}")

        # PDF 파일만 처리
        if not key.lower().endswith('.pdf'):
            logger.info("⏭️  Not a PDF file, skipping")
            return {
                'statusCode': 200,
                'body': json.dumps('Skipped: Not a PDF file')
            }

        # 메타데이터 추출
        metadata = extract_metadata_from_s3_path(key)
        logger.info(f"🏷️  Metadata: {metadata}")

        # 1. PDF 텍스트 추출
        text = extract_text_from_pdf(bucket, key)

        if not text or len(text) < 50:
            logger.warning("⚠️  텍스트가 너무 짧아 처리를 건너뜁니다")
            return {
                'statusCode': 200,
                'body': json.dumps('Skipped: Text too short')
            }

        # 2. 텍스트 청킹
        chunks = chunk_text(text)

        if not chunks:
            logger.warning("⚠️  유효한 청크가 없어 처리를 건너뜁니다")
            return {
                'statusCode': 200,
                'body': json.dumps('Skipped: No valid chunks')
            }

        # 3. 데이터베이스 저장
        save_to_database(bucket, key, text, chunks, metadata)

        logger.info("=" * 60)
        logger.info("✅ PDF 벡터화 완료")
        logger.info("=" * 60)

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'PDF processed successfully',
                'bucket': bucket,
                'key': key,
                'text_length': len(text),
                'chunk_count': len(chunks),
                'metadata': metadata
            })
        }

    except Exception as e:
        logger.error(f"❌ Error: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e)
            })
        }
