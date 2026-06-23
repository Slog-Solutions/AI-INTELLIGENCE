from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from ..db.session import SessionLocal
from ..models import Document, DocumentChunk, User
from ..services.document_processor import DocumentProcessor
from ..services.vectorstore import VectorStore
from ..services.rag_engine import RAGEngine
from ..services.audit_service import AuditService
from ..services.analytics_service import AnalyticsService
from ..schemas import DocumentUploadResponse, MultiUploadResponse, FileStatus
from ..core.dependencies import get_current_user
from ..core.rbac import require_roles
from pathlib import Path
from typing import List
import json
import logging
import io

logger = logging.getLogger(__name__)
router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def process_document_task(document_id: int, file_content: bytes, filename: str, category: str, source: str, user_id: int):
    db = SessionLocal()
    try:
        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            return

        # Use a temporary file-like object for parsing
        file_obj = io.BytesIO(file_content)
        saved_path = DocumentProcessor.save_upload(file_obj, filename)
        
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
            document.status = "error"
            db.commit()
            return

        chunks_with_metadata = DocumentProcessor.to_chunks(parsed_content, filename)
        if not chunks_with_metadata:
            document.status = "error"
            db.commit()
            return

        page_count = parsed_content.get("page_count", 0)
        chunk_count = len(chunks_with_metadata)
        metadata = DocumentProcessor.extract_metadata(saved_path, filename, category, source, page_count, chunk_count)
        
        document.metadata_json = json.dumps(metadata)
        document.page_count = page_count
        document.chunk_count = chunk_count
        document.preview_json = json.dumps(DocumentProcessor.generate_preview(parsed_content))
        
        # Analytics
        analytics = AnalyticsService.generate_analytics(saved_path, filename, parsed_content)
        document.analytics_json = json.dumps(analytics)

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

        vector_store.add_documents(texts=chunk_texts, metadatas=chunk_metadatas_for_vectorstore, ids=ids)

        for i, chunk_data in enumerate(chunks_with_metadata):
            db.add(DocumentChunk(
                document_id=document.id,
                chunk_text=chunk_data["content"],
                metadata_json=json.dumps(chunk_metadatas_for_vectorstore[i]),
                embedding_id=ids[i],
            ))
        
        document.status = "processed"
        db.commit()
        AuditService.create_entry(db, user_id, "upload_document", "documents", f"Processed {filename}")
    except Exception as e:
        logger.error(f"Async processing error for {filename}: {e}")
        if document:
            document.status = "error"
            db.commit()
    finally:
        db.close()

@router.post("/files", response_model=MultiUploadResponse)
async def upload_files(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    category: str = Form(...),
    source: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Super Admin", "Commanding Officer", "Instructor")),
):
    results = []
    for file in files:
        filename = Path(file.filename).name
        if not filename.lower().endswith((".xlsx", ".xls", ".csv", ".pdf", ".docx")):
            results.append(FileStatus(filename=filename, status="error", error="Unsupported file type"))
            continue

        try:
            # Initial DB entry
            document = Document(
                filename=filename,
                source=source,
                category=category,
                uploader_id=current_user.id,
                status="processing"
            )
            db.add(document)
            db.commit()
            db.refresh(document)

            # Read content to pass to background task
            content = await file.read()
            background_tasks.add_task(process_document_task, document.id, content, filename, category, source, current_user.id)
            
            results.append(FileStatus(filename=filename, status="processing", document_id=document.id))
        except Exception as e:
            results.append(FileStatus(filename=filename, status="error", error=str(e)))

    return MultiUploadResponse(files=results)

@router.post("/file", response_model=DocumentUploadResponse)
async def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    category: str = Form(...),
    source: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Super Admin", "Commanding Officer", "Instructor")),
):
    # Backward compatibility or single upload
    res = await upload_files(background_tasks, [file], category, source, db, current_user)
    file_res = res.files[0]
    if file_res.status == "error":
        raise HTTPException(status_code=400, detail=file_res.error)
    
    # Return a basic response since processing is async now
    return DocumentUploadResponse(
        id=file_res.document_id,
        filename=file_res.filename,
        category=category,
        source=source,
        status="processing",
        uploaded_at=datetime.utcnow()
    )
