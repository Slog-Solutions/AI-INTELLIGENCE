from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from sqlalchemy.orm import Session
from ..db.session import SessionLocal
from ..models import Document, DocumentChunk, User
from ..services.document_processor import DocumentProcessor
from ..services.vectorstore import VectorStore
from ..services.rag_engine import RAGEngine
from ..services.audit_service import AuditService
from ..schemas import DocumentUploadResponse
from ..core.dependencies import get_current_user
from ..core.rbac import require_roles
from pathlib import Path
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

    try:
        saved_path = DocumentProcessor.save_upload(file.file, filename)
        metadata = DocumentProcessor.extract_metadata(saved_path, filename, category, source)

        document = Document(
            filename=filename,
            source=source,
            category=category,
            uploader_id=current_user.id,
            metadata_json=json.dumps(metadata),
            status="processing"
        )
        db.add(document)
        db.commit()
        db.refresh(document)

        # Parsing
        if filename.lower().endswith((".xlsx", ".xls")):
            parsed = DocumentProcessor.parse_excel(saved_path)
        elif filename.lower().endswith(".csv"):
            parsed = DocumentProcessor.parse_csv(saved_path)
        elif filename.lower().endswith(".pdf"):
            parsed = DocumentProcessor.parse_pdf(saved_path)
        elif filename.lower().endswith(".docx"):
            parsed = DocumentProcessor.parse_docx(saved_path)
        
        # Generate Preview
        preview = DocumentProcessor.generate_preview(parsed)
        document.preview_json = json.dumps(preview)
        
        # Generate Chunks
        text_chunks = DocumentProcessor.to_chunks(parsed)
        if not text_chunks:
            document.status = "empty"
            db.commit()
            raise HTTPException(status_code=400, detail="No extractable text found in uploaded file")

        # Generate Summary using AI
        vector_store = VectorStore()
        rag = RAGEngine(vector_store)
        # Use first few chunks for summary context
        summary_context = "\n".join(text_chunks[:3])
        document.summary = rag.summarize_document(filename, summary_context)

        # Vector Store Upsert
        ids = [f"{document.id}-{i}" for i in range(len(text_chunks))]
        chunk_metadatas = [
            {
                "document_id": document.id,
                "filename": filename,
                "original_filename": filename,
                **metadata,
            }
            for i in range(len(text_chunks))
        ]
        vector_store.add_documents(
            texts=text_chunks,
            metadatas=chunk_metadatas,
            ids=ids,
        )

        # Save Chunks to DB
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
        db.refresh(document)

        AuditService.create_entry(db, current_user.id, "upload_document", "documents", f"Uploaded {filename}")

        return DocumentUploadResponse(
            id=document.id,
            filename=document.filename,
            category=document.category,
            source=document.source,
            status=document.status,
            summary=document.summary,
            preview=preview,
            uploaded_at=document.uploaded_at,
        )
    except Exception as e:
        logger.error(f"Upload Error: {str(e)}")
        if 'document' in locals():
            document.status = "error"
            db.commit()
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")
