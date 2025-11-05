
import os
import sys
from sqlalchemy import create_engine

# Add the app directory to the Python path to allow for absolute imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from database.models import Base
from utils.config import Settings

def init_database():
    """
    Initializes the database by creating all tables based on the defined models.
    """
    print("Initializing database...")
    settings = Settings()

    if not settings.DATABASE_URL:
        print("Error: DATABASE_URL not found in environment variables.")
        return

    try:
        engine = create_engine(str(settings.DATABASE_URL))
        
        print("Database engine created. Creating tables...")
        Base.metadata.create_all(bind=engine)
        print("Tables created successfully!")
        print("Database initialization complete.")
    except Exception as e:
        print(f"An error occurred during database initialization: {e}")

if __name__ == "__main__":
    init_database()
