


import sqlalchemy

from sqlalchemy import (

    create_engine,

    Column,

    Integer,

    String,

    Text,

    ForeignKey,

    DateTime,

)

from sqlalchemy.orm import declarative_base, relationship

from sqlalchemy.sql import func

from pgvector.sqlalchemy import Vector



Base = declarative_base()



class School(Base):

    __tablename__ = "schools"

    id = Column(Integer, primary_key=True, index=True)

    name = Column(String, unique=True, index=True, nullable=False)

    

    documents = relationship("Document", back_populates="school")

    rss_feeds = relationship("RssFeed", back_populates="school")

    default_contacts = relationship("DefaultContact", back_populates="school")



class Document(Base):

    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)

    school_id = Column(Integer, ForeignKey("schools.id"), nullable=False)

    

    source_url = Column(String, nullable=True)

    file_name = Column(String, nullable=True)

    category = Column(String, nullable=True)

    department = Column(String, nullable=True)

    

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    

    school = relationship("School", back_populates="documents")

    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")



class DocumentChunk(Base):

    __tablename__ = "document_chunks"

    id = Column(Integer, primary_key=True, index=True)

    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)

    

    chunk_text = Column(Text, nullable=False)

    embedding = Column(Vector(1536), nullable=False)

    

    document = relationship("Document", back_populates="chunks")



class RssFeed(Base):

    __tablename__ = "rss_feeds"

    id = Column(Integer, primary_key=True, index=True)

    school_id = Column(Integer, ForeignKey("schools.id"), nullable=False)

    url = Column(String, nullable=False)

    

    school = relationship("School", back_populates="rss_feeds")



class DefaultContact(Base):

    __tablename__ = "default_contacts"

    id = Column(Integer, primary_key=True, index=True)

    school_id = Column(Integer, ForeignKey("schools.id"), nullable=False)

    category = Column(String, index=True, nullable=False) # e.g., 'academics', 'scholarship'

    department = Column(String, nullable=False) # e.g., 'Academic Affairs Office'

    contact_info = Column(String, nullable=True) # e.g., '031-123-4567'



    school = relationship("School", back_populates="default_contacts")
