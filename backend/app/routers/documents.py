from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database.database import get_db
from app.services import document_service
from app.database import models
from app import schemas

router = APIRouter()

@router.get("/documents/by_source_url", response_model=schemas.Document)
async def get_document_by_source_url(source_url: str, db: Session = Depends(get_db)):
    """
    Retrieves a document by its source_url to check for existence.
    """
    document = db.query(models.Document).filter(models.Document.source_url == source_url).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return document

@router.post("/documents/add_by_text", status_code=201)
async def add_document_from_text(
    doc: schemas.DocumentCreateFromText, 
    db: Session = Depends(get_db)
):
    """
    Receives raw text data (e.g., from a crawler), and processes it.
    """
    # This will call a new function in document_service
    result = await document_service.process_text_document(
        doc=doc,
        db=db
    )
    return result
