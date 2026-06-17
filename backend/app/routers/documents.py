from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..db.session import SessionLocal
from ..models import Document, User
from ..schemas import DocumentOut
from ..core.rbac import require_roles

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
    return [
        DocumentOut(
            id=doc.id,
            filename=doc.filename,
            category=doc.category,
            source=doc.source,
            metadata=doc.metadata_json,
            uploaded_at=doc.uploaded_at,
        )
        for doc in docs
    ]
