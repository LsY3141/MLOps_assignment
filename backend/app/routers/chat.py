from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.services import rag_service
from app.database.database import get_db

# Pydantic model for the request body
class ChatQueryRequest(BaseModel):
    question: str
    school_id: int

router = APIRouter()

@router.post("/chat/query")
async def handle_chat_query(query: ChatQueryRequest, db: Session = Depends(get_db)):
    """
    Handles a user's chat query by calling the RAG service.
    """
    rag_response = await rag_service.get_rag_response(
        question=query.question, 
        school_id=query.school_id,
        db=db  # Pass the database session to the service
    )
    
    return {
        "question": query.question,
        "school_id": query.school_id,
        "answer": rag_response.answer,
        "source_documents": rag_response.source_documents
    }