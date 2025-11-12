from pydantic import BaseModel
from datetime import datetime
from typing import Optional

# --- Document Schemas ---
class Document(BaseModel):
    id: int
    school_id: int
    file_name: Optional[str] = None
    source_url: Optional[str] = None
    category: Optional[str] = None
    department: Optional[str] = None
    created_at: datetime
    class Config:
        from_attributes = True

class DocumentCreateFromText(BaseModel):
    school_id: int
    source_url: str
    category: str
    text: str
    department: Optional[str] = None

# --- School Schemas ---
class SchoolBase(BaseModel):
    name: str
class SchoolCreate(SchoolBase):
    pass
class School(SchoolBase):
    id: int
    class Config:
        from_attributes = True

# --- DocumentChunk Schemas ---
class DocumentChunk(BaseModel):
    id: int
    document_id: int
    chunk_text: str
    class Config:
        from_attributes = True

# --- RssFeed Schemas ---
class RssFeedBase(BaseModel):
    url: str
class RssFeedCreate(RssFeedBase):
    school_id: int
class RssFeed(RssFeedBase):
    id: int
    school_id: int
    class Config:
        from_attributes = True

# --- DefaultContact Schemas ---
class DefaultContactBase(BaseModel):
    category: str
    department: str
    contact_info: Optional[str] = None
class DefaultContactCreate(DefaultContactBase):
    school_id: int
class DefaultContact(DefaultContactBase):
    id: int
    school_id: int
    class Config:
        from_attributes = True