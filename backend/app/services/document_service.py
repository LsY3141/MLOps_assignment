"""
문서 처리 서비스
PDF/DOCX 파일의 텍스트 추출, 청킹, 임베딩
"""

import boto3
from typing import List, Dict, Any
from io import BytesIO
from PyPDF2 import PdfReader
from docx import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from app.services.llm_service import LLMService
from app.utils.config import settings


class DocumentService:
    """
    문서 처리 파이프라인 관리 클래스
    """
    
    def __init__(self):
        self.s3_client = boto3.client(
            's3',
            region_name=settings.AWS_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
        )
        
        self.llm_service = LLMService()
        
        # LangChain 텍스트 분할기
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""]
        )
    
    async def process_document(
        self,
        file_content: bytes,
        file_name: str,
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        문서 처리 파이프라인 실행
        
        Args:
            file_content: 파일 바이트 데이터
            file_name: 파일명
            metadata: 문서 메타데이터
            
        Returns:
            처리 결과
        """
        # 1. S3에 원본 파일 저장
        s3_key = await self._upload_to_s3(file_content, file_name, metadata)
        
        # 2. 텍스트 추출
        text = await self._extract_text(file_content, file_name)
        
        # 3. 텍스트 청킹
        chunks = self._chunk_text(text)
        
        # 4. 각 청크를 임베딩
        embeddings = await self.llm_service.batch_embed(chunks)
        
        # 5. DB에 저장할 데이터 구성
        document_data = {
            "s3_key": s3_key,
            "chunks": chunks,
            "embeddings": embeddings,
            "metadata": metadata,
            "total_chunks": len(chunks)
        }
        
        return document_data
    
    async def _upload_to_s3(
        self,
        file_content: bytes,
        file_name: str,
        metadata: Dict[str, Any]
    ) -> str:
        """
        S3에 원본 파일 업로드
        
        Args:
            file_content: 파일 내용
            file_name: 파일명
            metadata: 메타데이터
            
        Returns:
            S3 키
        """
        school_id = metadata.get("school_id", "unknown")
        s3_key = f"{school_id}/documents/{file_name}"
        
        try:
            # TODO: 실제 S3 업로드
            # self.s3_client.put_object(
            #     Bucket=settings.S3_BUCKET_NAME,
            #     Key=s3_key,
            #     Body=file_content,
            #     Metadata={
            #         "title": metadata.get("title", ""),
            #         "category": metadata.get("category", ""),
            #         "department": metadata.get("department", "")
            #     }
            # )
            
            return s3_key
            
        except Exception as e:
            raise Exception(f"S3 업로드 중 오류 발생: {str(e)}")
    
    async def _extract_text(self, file_content: bytes, file_name: str) -> str:
        """
        PDF 또는 DOCX에서 텍스트 추출
        
        Args:
            file_content: 파일 내용
            file_name: 파일명
            
        Returns:
            추출된 텍스트
        """
        file_ext = file_name.split(".")[-1].lower()
        
        try:
            if file_ext == "pdf":
                return self._extract_from_pdf(file_content)
            elif file_ext in ["docx", "doc"]:
                return self._extract_from_docx(file_content)
            else:
                raise ValueError(f"지원하지 않는 파일 형식: {file_ext}")
                
        except Exception as e:
            raise Exception(f"텍스트 추출 중 오류 발생: {str(e)}")
    
    def _extract_from_pdf(self, file_content: bytes) -> str:
        """
        PDF에서 텍스트 추출
        
        Args:
            file_content: PDF 파일 내용
            
        Returns:
            추출된 텍스트
        """
        pdf_file = BytesIO(file_content)
        pdf_reader = PdfReader(pdf_file)
        
        text_parts = []
        for page in pdf_reader.pages:
            text_parts.append(page.extract_text())
        
        return "\n\n".join(text_parts)
    
    def _extract_from_docx(self, file_content: bytes) -> str:
        """
        DOCX에서 텍스트 추출
        
        Args:
            file_content: DOCX 파일 내용
            
        Returns:
            추출된 텍스트
        """
        docx_file = BytesIO(file_content)
        doc = Document(docx_file)
        
        text_parts = []
        for paragraph in doc.paragraphs:
            if paragraph.text.strip():
                text_parts.append(paragraph.text)
        
        return "\n\n".join(text_parts)
    
    def _chunk_text(self, text: str) -> List[str]:
        """
        텍스트를 적절한 크기로 분할
        
        Args:
            text: 전체 텍스트
            
        Returns:
            분할된 텍스트 청크 리스트
        """
        chunks = self.text_splitter.split_text(text)
        
        # 너무 짧은 청크 제거
        chunks = [chunk for chunk in chunks if len(chunk.strip()) > 50]
        
        return chunks
    
    async def process_rss_content(
        self,
        title: str,
        content: str,
        link: str,
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        RSS 피드 콘텐츠 처리
        
        Args:
            title: 공지사항 제목
            content: 공지사항 내용
            link: 원본 링크
            metadata: 메타데이터
            
        Returns:
            처리 결과
        """
        # RSS 콘텐츠는 파일이 아니므로 S3 저장 건너뜀
        full_text = f"{title}\n\n{content}"
        
        # 텍스트 청킹
        chunks = self._chunk_text(full_text)
        
        # 임베딩
        embeddings = await self.llm_service.batch_embed(chunks)
        
        # DB 저장용 데이터 구성
        document_data = {
            "source": "rss",
            "link": link,
            "title": title,
            "chunks": chunks,
            "embeddings": embeddings,
            "metadata": metadata,
            "total_chunks": len(chunks)
        }
        
        return document_data
