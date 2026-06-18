from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..db.session import SessionLocal
from ..models import Document, User, Unit, AuditLog
from ..schemas import DocumentOut
from ..core.rbac import require_roles
from sqlalchemy import func
import json

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
        metadata = doc.metadata_json
        if isinstance(metadata, str) and metadata:
            try:
                metadata = json.loads(metadata)
            except:
                # Fallback to raw string if not JSON
                pass
        res.append(DocumentOut(
            id=doc.id,
            filename=doc.filename,
            category=doc.category,
            source=doc.source,
            metadata=metadata,
            uploaded_at=doc.uploaded_at,
        ))
    return res

@router.get("/stats")
def get_stats(db: Session = Depends(get_db), current_user: User = Depends(require_roles("Super Admin", "Commanding Officer", "Instructor", "Analyst"))):
    doc_count = db.query(func.count(Document.id)).scalar()
    unit_count = db.query(func.count(Unit.id)).scalar()
    alert_count = db.query(func.count(AuditLog.id)).filter(AuditLog.action.like("%error%")).scalar()
    
    # Intelligence specific stats
    categories = db.query(Document.category, func.count(Document.id)).group_by(Document.category).all()
    
    return {
        "documents_processed": doc_count,
        "active_units": unit_count,
        "ai_alerts": alert_count or 0,
        "categories": {cat: count for cat, count in categories}
    }
