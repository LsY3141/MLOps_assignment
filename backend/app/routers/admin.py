from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database.database import get_db
from app.services import document_service
from app.database import models
from app import schemas

router = APIRouter()

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