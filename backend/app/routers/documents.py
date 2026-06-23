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
from datetime import datetime, timedelta

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
        analytics = json.loads(doc.analytics_json) if doc.analytics_json else None
        
        res.append(DocumentOut(
            id=doc.id,
            filename=doc.filename,
            category=doc.category,
            source=doc.source,
            status=doc.status,
            summary=doc.summary,
            preview=preview,
            metadata=metadata,
            analytics=analytics,
            uploaded_at=doc.uploaded_at,
        ))
    return res

@router.get("/{document_id}", response_model=DocumentOut)
def get_document(document_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_roles("Super Admin", "Commanding Officer", "Instructor", "Analyst"))):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    metadata = json.loads(doc.metadata_json) if doc.metadata_json else {}
    preview = json.loads(doc.preview_json) if doc.preview_json else None
    analytics = json.loads(doc.analytics_json) if doc.analytics_json else None
    
    return DocumentOut(
        id=doc.id,
        filename=doc.filename,
        category=doc.category,
        source=doc.source,
        status=doc.status,
        summary=doc.summary,
        preview=preview,
        metadata=metadata,
        analytics=analytics,
        uploaded_at=doc.uploaded_at,
    )

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
    
    categories_raw = db.query(Document.category, func.count(Document.id)).group_by(Document.category).all()
    categories = [{"name": c[0], "value": c[1]} for c in categories_raw]
    recent_uploads = db.query(Document).order_by(Document.uploaded_at.desc()).limit(5).all()
    
    # Upload trends (last 7 days)
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    trends_raw = db.query(
        func.date(Document.uploaded_at).label('date'), 
        func.count(Document.id).label('count')
    ).filter(Document.uploaded_at >= seven_days_ago).group_by(func.date(Document.uploaded_at)).all()
    
    upload_trends = [{"date": str(t[0]), "uploads": t[1]} for t in trends_raw]

    # Aggregate risks and keywords from analytics_json
    all_risks = []
    all_keywords = {}
    
    docs_with_analytics = db.query(Document).filter(Document.analytics_json != None).all()
    for doc in docs_with_analytics:
        try:
            analytics_data = json.loads(doc.analytics_json)
            if "risks" in analytics_data:
                all_risks.extend(analytics_data["risks"])
            if "keywords" in analytics_data:
                for kw in analytics_data["keywords"]:
                    all_keywords[kw] = all_keywords.get(kw, 0) + 1
        except:
            continue

    keyword_frequency = [{"name": k, "value": v} for k, v in sorted(all_keywords.items(), key=lambda x: x[1], reverse=True)[:10]]

    return {
        "documents_processed": doc_count,
        "active_units": unit_count,
        "ai_alerts": error_count or 0,
        "categories": categories,
        "recent_uploads": [{"id": d.id, "filename": d.filename, "uploaded_at": d.uploaded_at, "status": d.status} for d in recent_uploads],
        "analytics": {
            "upload_trends": upload_trends,
            "risk_indicators": [{"label": r, "level": "Medium"} for r in all_risks[:5]],
            "keyword_frequency": keyword_frequency,
            "document_insights": f"Analyzed {len(docs_with_analytics)} documents with key findings in {len(all_keywords)} areas."
        }
    }
