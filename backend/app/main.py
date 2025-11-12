from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routers import chat, admin, documents

app = FastAPI(
    title="CampusMate API",
    description="API for the University Admin AI Chatbot 'CampusMate'",
    version="1.0.0",
)

# CORS (Cross-Origin Resource Sharing) configuration
origins = [
    "http://localhost:3000",
    "http://54.153.88.46:3000", # Allow access from the public IP
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    """
    Root endpoint for health check.
    """
    return {"status": "ok", "message": "Welcome to the CampusMate API!"}


app.include_router(chat.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(documents.router, prefix="/api")