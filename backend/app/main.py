from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routers import auth, upload, chat, users, documents
from .db.session import engine
from .db.base import Base

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="ATIP Backend",
    description="Army Training Intelligence Platform backend API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(upload.router, prefix="/upload", tags=["upload"])
app.include_router(chat.router, prefix="/chat", tags=["chat"])
app.include_router(users.router, prefix="/users", tags=["users"])
app.include_router(documents.router, prefix="/documents", tags=["documents"])

@app.get("/")
def root():
    return {"status": "ATIP backend running"}
