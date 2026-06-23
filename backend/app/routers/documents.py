from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..db.session import SessionLocal
from ..models import Document, User, Unit, AuditLog, DocumentChunk
from ..schemas import DocumentOut
from ..core.rbac import require_roles
from ..services.vectorstore import VectorStore
from sqlalchemy import func
import json
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/list", response_model=list[DocumentOut])
def list_documents(db: Session = Depends(get_db), current_user: User = Depends(require_roles("Super Admin", "Commanding Officer", "Instructor", "Analyst"))):
    docs = db.query(Document).order_by(Document.uploaded_at.desc()).all()
    res = []
    for doc in docs:
        metadata = json.loads(doc.metadata_json) if doc.metadata_json else {}
        preview = json.loads(doc.preview_json) if doc.preview_json else None
        
        res.append(DocumentOut(
            id=doc.id,
            filename=doc.filename,
            category=doc.category,
            source=doc.source,
            status=doc.status,
            summary=doc.summary,
            preview=preview,
            metadata=metadata,
            uploaded_at=doc.uploaded_at,
        ))
    return res

@router.delete("/{document_id}")
def delete_document(document_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_roles("Super Admin", "Commanding Officer"))):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    try:
        # Remove from Vector Store
        vector_store = VectorStore()
        chunks = db.query(DocumentChunk).filter(DocumentChunk.document_id == document_id).all()
        chunk_ids = [chunk.embedding_id for chunk in chunks if chunk.embedding_id]
        if chunk_ids:
            vector_store.collection.delete(ids=chunk_ids)
        
        # Database cascade will handle DocumentChunk removal
        db.delete(doc)
        db.commit()
        return {"message": "Document deleted successfully"}
    except Exception as e:
        logger.error(f"Delete Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Delete failed: {str(e)}")

@router.get("/stats")
def get_stats(db: Session = Depends(get_db), current_user: User = Depends(require_roles("Super Admin", "Commanding Officer", "Instructor", "Analyst"))):
    doc_count = db.query(func.count(Document.id)).scalar()
    unit_count = db.query(func.count(Unit.id)).scalar()
    error_count = db.query(func.count(Document.id)).filter(Document.status == "error").scalar()
    
    categories = db.query(Document.category, func.count(Document.id)).group_by(Document.category).all()
    recent_uploads = db.query(Document).order_by(Document.uploaded_at.desc()).limit(5).all()
    
    # Mock analytics for the intelligence dashboard (would be derived from actual document content in a full RAG system)
    analytics = {
        "readiness_score": 85,
        "trends": ["Increasing accuracy in field exercises", "Supply chain latency in Region B"],
        "risk_indicators": ["Low ammo stock in Unit 7", "High fatigue levels in Paratroopers"],
        "top_performers": ["Alpha Company", "Special Ops Group 3"]
    }
    
    return {
        "documents_processed": doc_count,
        "active_units": unit_count,
        "ai_alerts": error_count or 0,
        "categories": {cat: count for cat, count in categories},
        "recent_uploads": [{"filename": d.filename, "uploaded_at": d.uploaded_at, "status": d.status} for d in recent_uploads],
        "analytics": analytics
    }
