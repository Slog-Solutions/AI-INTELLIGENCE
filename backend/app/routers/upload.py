from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from sqlalchemy.orm import Session
from ..db.session import SessionLocal
from ..models import Document, DocumentChunk, User
from ..services.document_processor import DocumentProcessor
from ..services.vectorstore import VectorStore
from ..services.audit_service import AuditService
from ..schemas import DocumentUploadResponse
from ..core.dependencies import get_current_user
from ..core.rbac import require_roles
from ..config import UPLOAD_DIR
from pathlib import Path
import json

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/file", response_model=DocumentUploadResponse)
def upload_file(
    file: UploadFile = File(...),
    category: str = Form(...),
    source: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Super Admin", "Commanding Officer", "Instructor")),
):
    filename = Path(file.filename).name
    if not filename.lower().endswith((".xlsx", ".xls", ".csv", ".pdf", ".docx")):
        raise HTTPException(status_code=400, detail="Unsupported file type")

    saved_path = DocumentProcessor.save_upload(file.file, filename)
    metadata = DocumentProcessor.extract_metadata(saved_path, filename, category, source)

    document = Document(
        filename=metadata["saved_filename"],
        source=source,
        category=category,
        uploader_id=current_user.id,
        metadata_json=json.dumps(metadata),
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    if filename.lower().endswith((".xlsx", ".xls")):
        parsed = DocumentProcessor.parse_excel(saved_path)
    elif filename.lower().endswith(".csv"):
        parsed = DocumentProcessor.parse_csv(saved_path)
    elif filename.lower().endswith(".pdf"):
        parsed = DocumentProcessor.parse_pdf(saved_path)
    elif filename.lower().endswith(".docx"):
        parsed = DocumentProcessor.parse_docx(saved_path)
    else:
        raise HTTPException(status_code=400, detail="Unsupported file type")

    text_chunks = DocumentProcessor.to_chunks(parsed)
    if not text_chunks:
        document.status = "empty"
        db.commit()
        raise HTTPException(status_code=400, detail="No extractable text found in uploaded file")

    vector_store = VectorStore()
    ids = [f"{document.id}-{i}" for i in range(len(text_chunks))]
    chunk_metadatas = [
        {
            "document_id": document.id,
            "filename": document.filename,
            "citation": f"{document.filename}#chunk-{i + 1}",
            **metadata,
        }
        for i in range(len(text_chunks))
    ]
    vector_store.add_documents(
        texts=text_chunks,
        metadatas=chunk_metadatas,
        ids=ids,
    )

    for i, chunk_text in enumerate(text_chunks):
        db.add(
            DocumentChunk(
                document_id=document.id,
                chunk_text=chunk_text,
                metadata_json=json.dumps(chunk_metadatas[i]),
                embedding_id=ids[i],
            )
        )
    document.status = "processed"
    db.commit()

    AuditService.create_entry(db, current_user.id, "upload_document", "documents", f"Uploaded {filename} in category {category}")

    return DocumentUploadResponse(
        id=document.id,
        filename=document.filename,
        category=document.category,
        source=document.source,
        uploaded_at=document.uploaded_at,
    )
