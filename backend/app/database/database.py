from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.utils.config import DATABASE_URL

# Create the SQLAlchemy engine using the URL from our config
engine = create_engine(DATABASE_URL)

# Create a configured "Session" class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Dependency function that FastAPI will use to get a DB session per request
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
