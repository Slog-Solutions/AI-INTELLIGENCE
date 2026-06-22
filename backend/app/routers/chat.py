from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..db.session import SessionLocal
from ..services.vectorstore import VectorStore
from ..services.rag_engine import RAGEngine
from ..services.audit_service import AuditService
from ..schemas import ChatRequest, ChatResponse, SourceCitation
from ..core.dependencies import get_current_user
from ..core.rbac import require_roles
from typing import List
import re

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
        
        confidence_match = re.search(r"Confidence: (High|Medium|Low)", response["answer"])
        confidence = confidence_match.group(1) if confidence_match else None
        if confidence_match:
            response["answer"] = response["answer"].replace(confidence_match.group(0), "").strip()

        structured_sources: List[SourceCitation] = []
        for src_str in response["sources"]:
            match = re.match(r"(.*?)(?: \(Page (\d+)\))?", src_str)
            if match:
                filename = match.group(1).strip()
                page_number = int(match.group(2)) if match.group(2) else None
                structured_sources.append(SourceCitation(filename=filename, page_number=page_number))
            else:
                structured_sources.append(SourceCitation(filename=src_str))

        return ChatResponse(
            answer=response["answer"], 
            sources=structured_sources,
            confidence=confidence
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
