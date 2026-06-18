from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..db.session import SessionLocal
from ..services.vectorstore import VectorStore
from ..services.rag_engine import RAGEngine
from ..services.audit_service import AuditService
from ..schemas import ChatRequest, ChatResponse
from ..core.dependencies import get_current_user
from ..core.rbac import require_roles

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/query", response_model=ChatResponse)
def query_chat(request: ChatRequest, db: Session = Depends(get_db), current_user=Depends(require_roles("Super Admin", "Commanding Officer", "Instructor", "Analyst"))):
    vector_store = VectorStore()
    rag = RAGEngine(vector_store)
    try:
        response = rag.query(request.query)
        AuditService.create_entry(db, current_user.id, "chat_query", "chat", f"Query: {request.query}")
        return ChatResponse(
            answer=response["answer"], 
            sources=response["sources"]
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
