"""
S3에 이미 업로드된 PDF 파일들을 벡터화하는 배치 스크립트

사용법:
    python batch_vectorize_s3_pdfs.py --school-id 1 --category academic

옵션:
    --school-id: 학교 ID (필수)
    --category: 문서 카테고리 (선택)
    --department: 담당 부서 (선택)
    --prefix: S3 폴더 경로 (예: documents/school_1/)
    --dry-run: 실제 처리 없이 목록만 확인
"""

import os
import sys
import argparse
import boto3
from io import BytesIO
from typing import List, Dict, Any
import logging

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.database.database import SessionLocal
from app.services.document_service import document_service
from app.services.llm_service import llm_service
from app.database import models
from PyPDF2 import PdfReader
from langchain.text_splitter import RecursiveCharacterTextSplitter

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class S3PDFVectorizer:
    """S3의 기존 PDF를 벡터화하는 클래스"""

    def __init__(self, bucket_name: str):
        """
        Args:
            bucket_name: S3 버킷 이름
        """
        self.bucket_name = bucket_name
        self.s3_client = boto3.client(
            's3',
            region_name=os.getenv("AWS_REGION", "us-west-1")
        )
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            separators=["\n\n", "\n", ". ", "! ", "? ", " ", ""]
        )

    def list_pdfs(self, prefix: str = "") -> List[Dict[str, Any]]:
        """
        S3 버킷에서 PDF 파일 목록을 가져옵니다.

        Args:
            prefix: S3 폴더 경로 (예: "documents/")

        Returns:
            PDF 파일 정보 리스트
        """
        logger.info(f"📂 Listing PDFs from s3://{self.bucket_name}/{prefix}")

        pdf_files = []
        paginator = self.s3_client.get_paginator('list_objects_v2')

        for page in paginator.paginate(Bucket=self.bucket_name, Prefix=prefix):
            if 'Contents' not in page:
                continue

            for obj in page['Contents']:
                key = obj['Key']
                if key.lower().endswith('.pdf'):
                    pdf_files.append({
                        'key': key,
                        'size': obj['Size'],
                        'last_modified': obj['LastModified']
                    })

        logger.info(f"✅ Found {len(pdf_files)} PDF files")
        return pdf_files

    def download_pdf(self, s3_key: str) -> BytesIO:
        """
        S3에서 PDF 파일을 다운로드합니다.

        Args:
            s3_key: S3 객체 키

        Returns:
            PDF 파일 스트림
        """
        logger.info(f"⬇️  Downloading: {s3_key}")

        response = self.s3_client.get_object(Bucket=self.bucket_name, Key=s3_key)
        return BytesIO(response['Body'].read())

    def extract_text_from_pdf(self, pdf_stream: BytesIO) -> str:
        """
        PDF에서 텍스트를 추출합니다.

        Args:
            pdf_stream: PDF 파일 스트림

        Returns:
            추출된 텍스트
        """
        reader = PdfReader(pdf_stream)
        text = ""

        for i, page in enumerate(reader.pages):
            page_text = page.extract_text() or ""
            text += f"[페이지 {i+1}]\n{page_text}\n\n"

        logger.info(f"📄 Extracted {len(text)} characters from {len(reader.pages)} pages")
        return text.strip()

    def process_pdf(
        self,
        s3_key: str,
        school_id: int,
        category: str,
        department: str = None,
        db_session = None,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        PDF 파일을 처리하여 벡터화합니다.

        Args:
            s3_key: S3 파일 경로
            school_id: 학교 ID
            category: 문서 카테고리
            department: 담당 부서
            db_session: 데이터베이스 세션
            dry_run: True면 실제 저장하지 않음

        Returns:
            처리 결과
        """
        try:
            # 1. S3에서 PDF 다운로드
            pdf_stream = self.download_pdf(s3_key)

            # 2. 텍스트 추출
            text = self.extract_text_from_pdf(pdf_stream)

            if not text or len(text) < 50:
                return {
                    "status": "skipped",
                    "reason": "텍스트가 너무 짧음",
                    "s3_key": s3_key
                }

            # 3. 텍스트 청킹
            chunks = self.text_splitter.split_text(text)
            chunks = [c.strip() for c in chunks if c.strip() and len(c.strip()) > 50]

            logger.info(f"✂️  Created {len(chunks)} chunks")

            if dry_run:
                return {
                    "status": "dry_run",
                    "s3_key": s3_key,
                    "text_length": len(text),
                    "chunk_count": len(chunks)
                }

            # 4. 임베딩 생성
            embeddings = llm_service.get_embeddings(chunks)

            if not embeddings:
                logger.warning("⚠️  임베딩 생성 실패 - 키워드 검색만 사용 가능")
                # 임베딩 없이도 문서는 저장 (키워드 검색용)
                embeddings = None

            # 5. DB에 문서 레코드 생성
            filename = s3_key.split('/')[-1]
            s3_url = f"https://{self.bucket_name}.s3.{os.getenv('AWS_REGION', 'us-west-1')}.amazonaws.com/{s3_key}"

            new_document = models.Document(
                school_id=school_id,
                category=category,
                file_name=filename,
                s3_url=s3_url,
                source_url=s3_url,
                department=department
            )

            db_session.add(new_document)
            db_session.commit()
            db_session.refresh(new_document)

            logger.info(f"💾 Document saved with ID: {new_document.id}")

            # 6. 청크와 임베딩 저장
            chunk_count = 0
            for i, chunk_text in enumerate(chunks):
                # 임베딩이 없으면 None으로 저장 (키워드 검색용)
                embedding = embeddings[i] if embeddings else None

                chunk_record = models.DocumentChunk(
                    document_id=new_document.id,
                    chunk_text=chunk_text,
                    embedding=embedding
                )
                db_session.add(chunk_record)
                chunk_count += 1

            db_session.commit()
            logger.info(f"✅ Saved {chunk_count} chunks")

            return {
                "status": "success",
                "s3_key": s3_key,
                "document_id": new_document.id,
                "text_length": len(text),
                "chunk_count": chunk_count
            }

        except Exception as e:
            logger.error(f"❌ Error processing {s3_key}: {e}")
            if db_session and 'new_document' in locals():
                db_session.rollback()

            return {
                "status": "error",
                "s3_key": s3_key,
                "error": str(e)
            }


def main():
    parser = argparse.ArgumentParser(description='S3의 기존 PDF를 벡터화합니다.')
    parser.add_argument('--school-id', type=int, required=True, help='학교 ID')
    parser.add_argument('--category', type=str, default='general', help='문서 카테고리')
    parser.add_argument('--department', type=str, help='담당 부서')
    parser.add_argument('--prefix', type=str, default='documents/', help='S3 폴더 경로')
    parser.add_argument('--dry-run', action='store_true', help='실제 처리 없이 목록만 확인')

    args = parser.parse_args()

    # 환경 변수 확인
    bucket_name = os.getenv("S3_BUCKET_NAME")
    if not bucket_name:
        logger.error("❌ S3_BUCKET_NAME 환경 변수가 설정되지 않았습니다.")
        sys.exit(1)

    logger.info("=" * 60)
    logger.info("🚀 S3 PDF 벡터화 배치 작업 시작")
    logger.info("=" * 60)
    logger.info(f"버킷: {bucket_name}")
    logger.info(f"학교 ID: {args.school_id}")
    logger.info(f"카테고리: {args.category}")
    logger.info(f"경로: {args.prefix}")
    logger.info(f"Dry Run: {args.dry_run}")
    logger.info("=" * 60)

    # S3 벡터라이저 초기화
    vectorizer = S3PDFVectorizer(bucket_name)

    # PDF 목록 가져오기
    pdf_files = vectorizer.list_pdfs(args.prefix)

    if not pdf_files:
        logger.warning("⚠️  처리할 PDF 파일이 없습니다.")
        return

    # 데이터베이스 세션 생성
    db = SessionLocal()

    try:
        results = {
            "success": 0,
            "error": 0,
            "skipped": 0,
            "dry_run": 0
        }

        # 각 PDF 처리
        for i, pdf_info in enumerate(pdf_files, 1):
            logger.info(f"\n{'='*60}")
            logger.info(f"📝 Processing [{i}/{len(pdf_files)}]: {pdf_info['key']}")
            logger.info(f"{'='*60}")

            result = vectorizer.process_pdf(
                s3_key=pdf_info['key'],
                school_id=args.school_id,
                category=args.category,
                department=args.department,
                db_session=db,
                dry_run=args.dry_run
            )

            results[result["status"]] += 1

            if result["status"] == "success":
                logger.info(f"✅ 성공: Document ID {result['document_id']}")
            elif result["status"] == "error":
                logger.error(f"❌ 실패: {result.get('error')}")
            elif result["status"] == "skipped":
                logger.warning(f"⏭️  건너뜀: {result.get('reason')}")

        # 최종 결과 출력
        logger.info("\n" + "=" * 60)
        logger.info("📊 최종 결과")
        logger.info("=" * 60)
        logger.info(f"✅ 성공: {results['success']}")
        logger.info(f"❌ 실패: {results['error']}")
        logger.info(f"⏭️  건너뜀: {results['skipped']}")
        if args.dry_run:
            logger.info(f"🔍 Dry Run: {results['dry_run']}")
        logger.info("=" * 60)

    finally:
        db.close()


if __name__ == "__main__":
    main()
