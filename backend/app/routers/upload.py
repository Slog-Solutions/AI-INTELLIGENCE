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
        
        parsed_content = {}
        if filename.lower().endswith((".xlsx", ".xls")):
            parsed_content = DocumentProcessor.parse_excel(saved_path)
        elif filename.lower().endswith(".csv"):
            parsed_content = DocumentProcessor.parse_csv(saved_path)
        elif filename.lower().endswith(".pdf"):
            parsed_content = DocumentProcessor.parse_pdf(saved_path)
        elif filename.lower().endswith(".docx"):
            parsed_content = DocumentProcessor.parse_docx(saved_path)
        
        if "error" in parsed_content:
            raise HTTPException(status_code=422, detail=f"Document parsing failed: {parsed_content['error']}")

        chunks_with_metadata = DocumentProcessor.to_chunks(parsed_content, filename)
        if not chunks_with_metadata:
            raise HTTPException(status_code=400, detail="No extractable text found in uploaded file")

        page_count = parsed_content.get("page_count", 0)
        chunk_count = len(chunks_with_metadata)
        metadata = DocumentProcessor.extract_metadata(saved_path, filename, category, source, page_count, chunk_count)

        document = Document(
            filename=filename,
            source=source,
            category=category,
            uploader_id=current_user.id,
            metadata_json=json.dumps(metadata),
            status="processing",
            page_count=page_count,
            chunk_count=chunk_count,
        )
        db.add(document)
        db.commit()
        db.refresh(document)

        preview = DocumentProcessor.generate_preview(parsed_content)
        document.preview_json = json.dumps(preview)
        
        vector_store = VectorStore()
        rag = RAGEngine(vector_store)
        summary_context = "\n".join([c["content"] for c in chunks_with_metadata[:3]])
        document.summary = rag.summarize_document(filename, summary_context)

        ids = [f"{document.id}-{i}" for i in range(len(chunks_with_metadata))]
        chunk_texts = [c["content"] for c in chunks_with_metadata]
        chunk_metadatas_for_vectorstore = []
        for i, chunk_data in enumerate(chunks_with_metadata):
            chunk_metadata = {
                "document_id": document.id,
                "filename": filename,
                "original_filename": filename,
                **metadata,
                **chunk_data["metadata"],
            }
            chunk_metadatas_for_vectorstore.append(chunk_metadata)

        vector_store.add_documents(
            texts=chunk_texts,
            metadatas=chunk_metadatas_for_vectorstore,
            ids=ids,
        )

        for i, chunk_data in enumerate(chunks_with_metadata):
            db.add(
                DocumentChunk(
                    document_id=document.id,
                    chunk_text=chunk_data["content"],
                    metadata_json=json.dumps(chunk_metadatas_for_vectorstore[i]),
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
            page_count=document.page_count,
            chunk_count=document.chunk_count,
            uploaded_at=document.uploaded_at,
        )
    except HTTPException as he:
        if 'document' in locals():
            document.status = "error"
            db.commit()
        raise he
    except Exception as e:
        logger.error(f"Upload Error: {str(e)}")
        if 'document' in locals():
            document.status = "error"
            db.commit()
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")
