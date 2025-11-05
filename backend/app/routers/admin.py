"""
관리자 문서 관리 API 라우터
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

router = APIRouter()


class DocumentMetadata(BaseModel):
    """
    문서 메타데이터 모델
    """
    title: str = Field(..., description="문서 제목")
    category: str = Field(..., description="카테고리 (학사/장학/시설 등)")
    department: str = Field(..., description="담당 부서")
    contact: str = Field(..., description="담당 부서 연락처")
    school_id: str = Field(..., description="학교 ID")


class DocumentResponse(BaseModel):
    """
    문서 응답 모델
    """
    document_id: str
    title: str
    category: str
    department: str
    contact: str
    upload_date: datetime
    status: str


@router.post("/document", response_model=DocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    title: str = Form(...),
    category: str = Form(...),
    department: str = Form(...),
    contact: str = Form(...),
    school_id: str = Form(...)
):
    """
    관리자 문서 업로드
    
    - **file**: PDF 또는 DOCX 파일
    - **title**: 문서 제목
    - **category**: 카테고리
    - **department**: 담당 부서
    - **contact**: 연락처
    - **school_id**: 학교 ID
    
    Returns:
        업로드된 문서 정보
    """
    # 파일 형식 검증
    allowed_extensions = [".pdf", ".docx", ".doc"]
    file_ext = "." + file.filename.split(".")[-1].lower()
    
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"지원하지 않는 파일 형식입니다. 허용: {', '.join(allowed_extensions)}"
        )
    
    try:
        # TODO: 실제 문서 처리 파이프라인 구현
        # 1. S3에 원본 파일 저장
        # 2. 텍스트 추출
        # 3. LangChain으로 청킹
        # 4. Bedrock Titan으로 임베딩
        # 5. RDS에 벡터 및 메타데이터 저장
        
        # 임시 응답
        return DocumentResponse(
            document_id="temp_doc_123",
            title=title,
            category=category,
            department=department,
            contact=contact,
            upload_date=datetime.now(),
            status="processing"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"문서 업로드 중 오류 발생: {str(e)}")


@router.get("/documents", response_model=List[DocumentResponse])
async def list_documents(
    school_id: str,
    category: Optional[str] = None,
    skip: int = 0,
    limit: int = 20
):
    """
    문서 목록 조회
    
    Args:
        school_id: 학교 ID
        category: 카테고리 필터 (선택)
        skip: 건너뛸 문서 수
        limit: 반환할 최대 문서 수
        
    Returns:
        문서 목록
    """
    # TODO: 실제 DB 조회 구현
    return []


@router.delete("/document/{document_id}")
async def delete_document(document_id: str, school_id: str):
    """
    문서 삭제
    
    Args:
        document_id: 문서 ID
        school_id: 학교 ID
        
    Returns:
        삭제 결과
    """
    # TODO: 문서 삭제 구현
    # 1. DB에서 벡터 및 메타데이터 삭제
    # 2. S3에서 원본 파일 삭제
    
    return {
        "status": "success",
        "message": f"문서 {document_id}가 삭제되었습니다."
    }


@router.post("/rss")
async def add_rss_feed(
    school_id: str = Form(...),
    feed_url: str = Form(...),
    category: str = Form(...),
    department: str = Form(...),
    contact: str = Form(...)
):
    """
    RSS 피드 추가
    
    Args:
        school_id: 학교 ID
        feed_url: RSS 피드 URL
        category: 카테고리
        department: 담당 부서
        contact: 연락처
        
    Returns:
        RSS 피드 등록 결과
    """
    # TODO: RSS 피드 DB에 등록
    return {
        "status": "success",
        "message": "RSS 피드가 등록되었습니다.",
        "feed_url": feed_url
    }


@router.get("/rss")
async def list_rss_feeds(school_id: str):
    """
    등록된 RSS 피드 목록 조회
    
    Args:
        school_id: 학교 ID
        
    Returns:
        RSS 피드 목록
    """
    # TODO: RSS 피드 목록 조회
    return []
