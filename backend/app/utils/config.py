import os
from dotenv import load_dotenv

# Construct the path to the .env file located in the parent 'backend' directory
dotenv_path = os.path.join(os.path.dirname(__file__), '..', '..', '.env')
load_dotenv(dotenv_path=dotenv_path)

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable not set. Please create a .env file in the 'backend' directory.")

# Other settings for AWS, Bedrock, etc., can be added here later.