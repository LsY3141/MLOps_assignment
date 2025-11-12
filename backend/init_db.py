
import os
import sys
from sqlalchemy import create_engine
import argparse # Import argparse to handle command-line arguments

# Add the 'app' directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'app')))

from database.models import Base
from utils.config import DATABASE_URL

def init_database(recreate: bool = False):
    """
    Initializes the database. If recreate is True, drops all tables first.
    """
    print("Initializing database...")

    if not DATABASE_URL:
        print("Error: DATABASE_URL not found. Check your .env file and config.py.")
        return

    try:
        engine = create_engine(DATABASE_URL)
        
        if recreate:
            print("Dropping all tables...")
            Base.metadata.drop_all(bind=engine)
            print("Tables dropped.")

        print("Database engine created. Creating tables...")
        Base.metadata.create_all(bind=engine)
        print("Tables created successfully!")
        print("Database initialization complete.")
    except Exception as e:
        print(f"An error occurred during database initialization: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Initialize the database.")
    parser.add_argument(
        '--recreate',
        action='store_true',
        help='Drop all tables and recreate them.'
    )
    args = parser.parse_args()
    
    init_database(recreate=args.recreate)