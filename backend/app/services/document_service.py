import io
from typing import Optional
from fastapi import UploadFile
from PyPDF2 import PdfReader
import docx
from sqlalchemy.orm import Session
from app.database import models
from app import schemas
from langchain.text_splitter import RecursiveCharacterTextSplitter
from . import llm_service

def extract_text_from_file(file: UploadFile) -> Optional[str]:
    # ... (existing function)
    text = ""
    try:
        file.file.seek(0)
        if file.filename.endswith(".pdf"):
            pdf_stream = io.BytesIO(file.file.read())
            reader = PdfReader(pdf_stream)
            for page in reader.pages:
                text += page.extract_text() or ""
        elif file.filename.endswith(".docx"):
            doc_stream = io.BytesIO(file.file.read())
            doc = docx.Document(doc_stream)
            for para in doc.paragraphs:
                text += para.text + "\n"
        else:
            content_bytes = file.file.read()
            text = content_bytes.decode("utf-8")
        return text
    except Exception as e:
        print(f"Error extracting text from {file.filename}: {e}")
        return None
    finally:
        file.file.seek(0)

async def process_document(school_id: int, category: str, file: UploadFile, db: Session):
    # ... (existing function)
    print("--- Starting Document Processing (File) ---")
    
    new_document = models.Document(
        school_id=school_id, category=category, file_name=file.filename)
    db.add(new_document)
    db.commit()
    db.refresh(new_document)
    print(f"--- Saved new document record with ID: {new_document.id} ---")

    extracted_text = extract_text_from_file(file)
    
    if not extracted_text:
        db.delete(new_document)
        db.commit()
        return {"error": "Failed to extract text from file or file is empty."}

    return await _chunk_embed_and_store(extracted_text, new_document, db)

async def process_text_document(doc: schemas.DocumentCreateFromText, db: Session):
    """
    Processes a document from raw text, reusing the core logic.
    """
    print("--- Starting Document Processing (Text) ---")
    
    new_document = models.Document(
        school_id=doc.school_id,
        category=doc.category,
        source_url=doc.source_url,
        department=doc.department
    )
    db.add(new_document)
    db.commit()
    db.refresh(new_document)
    print(f"--- Saved new document record with ID: {new_document.id} ---")

    if not doc.text:
        db.delete(new_document)
        db.commit()
        return {"error": "Text content is empty."}

    return await _chunk_embed_and_store(doc.text, new_document, db)

async def _chunk_embed_and_store(text: str, document: models.Document, db: Session):
    """
    Private helper function to handle the common logic of chunking, embedding, and storing.
    """
    # Chunk the text
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000, chunk_overlap=200, length_function=len)
    chunks = text_splitter.split_text(text)
    print(f"--- Text split into {len(chunks)} chunks ---")

    # Generate embeddings for chunks
    embeddings = llm_service.get_embeddings(chunks)
    if not embeddings or len(embeddings) != len(chunks):
        db.delete(document)
        db.commit()
        return {"error": "Failed to generate embeddings for document chunks."}
    print(f"--- Generated {len(embeddings)} embeddings ---")

    # Store chunks and embeddings in the database
    for i, chunk_text in enumerate(chunks):
        new_chunk = models.DocumentChunk(
            document_id=document.id,
            chunk_text=chunk_text,
            embedding=embeddings[i]
        )
        db.add(new_chunk)
    
    db.commit()
    print(f"--- Successfully saved {len(chunks)} chunks to the database ---")
    
    return {
        "message": "Document fully processed and stored successfully.",
        "document_id": document.id,
        "source": document.file_name or document.source_url,
        "num_chunks": len(chunks)
    }