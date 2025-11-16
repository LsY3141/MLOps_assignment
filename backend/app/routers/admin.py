from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel
from app.database.database import get_db
from app.services import document_service
from app.database import models
from app import schemas
import boto3
import os
from datetime import datetime

router = APIRouter()

# Presigned URL 요청 모델
class PresignedURLRequest(BaseModel):
    school_id: int
    category: str
    file_name: str
    department: str = None

@router.post("/admin/schools", response_model=schemas.School)
def create_school(school: schemas.SchoolCreate, db: Session = Depends(get_db)):
    # ... (implementation)
    db_school = models.School(name=school.name)
    db.add(db_school)
    db.commit()
    db.refresh(db_school)
    return db_school

@router.post("/admin/rss-feeds", response_model=schemas.RssFeed)
def create_rss_feed(feed: schemas.RssFeedCreate, db: Session = Depends(get_db)):
    # ... (implementation)
    db_school = db.query(models.School).filter(models.School.id == feed.school_id).first()
    if not db_school:
        raise HTTPException(status_code=404, detail=f"School with id {feed.school_id} not found")
    db_feed = models.RssFeed(**feed.model_dump())
    db.add(db_feed)
    db.commit()
    db.refresh(db_feed)
    return db_feed

@router.post("/admin/default-contacts", response_model=schemas.DefaultContact)
def create_default_contact(contact: schemas.DefaultContactCreate, db: Session = Depends(get_db)):
    """
    Creates a new default contact for a category.
    """
    db_school = db.query(models.School).filter(models.School.id == contact.school_id).first()
    if not db_school:
        raise HTTPException(status_code=404, detail=f"School with id {contact.school_id} not found")
    
    db_contact = models.DefaultContact(**contact.model_dump())
    db.add(db_contact)
    db.commit()
    db.refresh(db_contact)
    return db_contact

@router.get("/admin/documents", response_model=List[schemas.Document])
async def list_documents(db: Session = Depends(get_db)):
    # ... (implementation)
    documents = db.query(models.Document).all()
    return documents

@router.get("/admin/chunks", response_model=List[schemas.DocumentChunk])
async def list_chunks(db: Session = Depends(get_db)):
    # ... (implementation)
    chunks = db.query(models.DocumentChunk).all()
    return chunks

@router.post("/admin/documents/upload")
async def upload_document(
    school_id: int = Form(...),
    category: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    # ... (implementation)
    result = await document_service.process_document(
        school_id=school_id,
        category=category,
        file=file,
        db=db
    )
    return result


@router.post("/documents/presigned-url")
async def generate_presigned_url(request: PresignedURLRequest):
    """
    S3에 파일을 직접 업로드하기 위한 Presigned URL을 생성합니다.

    프론트엔드에서 이 URL로 PUT 요청을 보내면 S3에 파일이 업로드되고,
    S3 이벤트 트리거가 Lambda를 실행하여 자동으로 벡터화 처리됩니다.

    Args:
        request: Presigned URL 요청 정보

    Returns:
        upload_url: S3 Presigned URL
        s3_key: S3 객체 키
    """
    try:
        # S3 클라이언트 초기화
        s3_client = boto3.client(
            's3',
            region_name=os.getenv("AWS_REGION", "us-west-1")
        )

        bucket_name = os.getenv("S3_BUCKET_NAME")
        if not bucket_name:
            raise HTTPException(status_code=500, detail="S3_BUCKET_NAME not configured")

        # S3 키 생성: documents/{school_id}/{category}/{timestamp}_{filename}
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        s3_key = f"documents/{request.school_id}/{request.category}/{timestamp}_{request.file_name}"

        # Presigned URL 생성 (15분 유효)
        presigned_url = s3_client.generate_presigned_url(
            'put_object',
            Params={
                'Bucket': bucket_name,
                'Key': s3_key,
                'ContentType': 'application/pdf'
            },
            ExpiresIn=900  # 15분
        )

        return {
            "upload_url": presigned_url,
            "s3_key": s3_key,
            "bucket": bucket_name,
            "expires_in": 900
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate presigned URL: {str(e)}")