"""
ATIP Upload Router
===================
Handles multi-file uploads (up to 5 simultaneously, 300+ pages each).
Processing runs in background tasks:
  1. Parse document (PDF/DOCX/Excel/CSV)
  2. Intelligent chunking (heading/paragraph/table/sentence-overlap aware)
  3. Entity extraction (officers, ranks, units, operations, weapons…)
  4. BGE embedding + ChromaDB upsert (ALL documents share one collection)
  5. BM25 index invalidation (rebuilt lazily on next query)
  6. Generate AI summary via Ollama
  7. Persist to PostgreSQL (Document + DocumentChunk records)
"""

from datetime import datetime
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from pathlib import Path
from typing import List
import io
import json
import logging

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
from ..config import CHUNK_SIZE, CHUNK_OVERLAP, MAX_SIMULTANEOUS_DOCS

logger = logging.getLogger(__name__)
router = APIRouter()

# ── DB Dependency ──────────────────────────────────────────────────────────────
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Background Processing Task ─────────────────────────────────────────────────
def process_document_task(
    document_id: int,
    file_content: bytes,
    filename: str,
    category: str,
    source: str,
    user_id: int,
):
    """
    Full processing pipeline for a single uploaded document.
    Runs asynchronously via FastAPI BackgroundTasks.
    """
    db = SessionLocal()
    document = None
    try:
        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            logger.error(f"Document ID {document_id} not found in DB")
            return

        # ── Step 1: Save file ──────────────────────────────────────────────────
        file_obj = io.BytesIO(file_content)
        saved_path = DocumentProcessor.save_upload(file_obj, filename)
        logger.info(f"Saved {filename} → {saved_path}")

        # ── Step 2: Parse document ─────────────────────────────────────────────
        ext = filename.lower()
        parsed_content: dict = {}
        if ext.endswith((".xlsx", ".xls")):
            parsed_content = DocumentProcessor.parse_excel(saved_path)
        elif ext.endswith(".csv"):
            parsed_content = DocumentProcessor.parse_csv(saved_path)
        elif ext.endswith(".pdf"):
            parsed_content = DocumentProcessor.parse_pdf(saved_path)
        elif ext.endswith(".docx"):
            parsed_content = DocumentProcessor.parse_docx(saved_path)
        else:
            document.status = "error"
            db.commit()
            return

        if parsed_content.get("error"):
            logger.error(f"Parse error for {filename}: {parsed_content['error']}")
            document.status = "error"
            db.commit()
            return

        # ── Step 3: Intelligent chunking ───────────────────────────────────────
        chunks_with_meta = DocumentProcessor.to_chunks(
            parsed_content,
            filename,
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
        )

        if not chunks_with_meta:
            logger.warning(f"No chunks produced for {filename}")
            document.status = "error"
            db.commit()
            return

        # ── Step 4: Extract document-level entities ────────────────────────────
        full_text = parsed_content.get("full_text", "")
        if not full_text and parsed_content.get("type") in ("excel", "csv"):
            # Build a text representation for entity extraction
            full_text = " ".join([c["content"] for c in chunks_with_meta[:10]])
        doc_entities = DocumentProcessor.extract_entities(full_text[:20000])

        page_count = parsed_content.get("page_count", 0)
        chunk_count = len(chunks_with_meta)

        # ── Step 5: Metadata & analytics ──────────────────────────────────────
        doc_metadata = DocumentProcessor.extract_metadata(
            saved_path, filename, category, source,
            page_count, chunk_count, doc_entities,
        )
        document.metadata_json = json.dumps(doc_metadata)
        document.page_count = page_count
        document.chunk_count = chunk_count
        document.preview_json = json.dumps(DocumentProcessor.generate_preview(parsed_content))

        analytics = AnalyticsService.generate_analytics(saved_path, filename, parsed_content)
        document.analytics_json = json.dumps(analytics)

        # ── Step 6: AI Summary ────────────────────────────────────────────────
        try:
            vector_store = VectorStore()
            rag = RAGEngine(vector_store)
            summary_context = " ".join([c["content"] for c in chunks_with_meta[:5]])
            document.summary = rag.summarize_document(filename, summary_context)
            logger.info(f"Summary generated for {filename}")
        except Exception as e:
            logger.warning(f"Summary generation failed for {filename}: {e}")
            document.summary = f"Summary unavailable: {e}"

        # ── Step 7: Vectorise and index ────────────────────────────────────────
        vector_store = VectorStore()
        ids: List[str] = []
        texts: List[str] = []
        metadatas: List[dict] = []

        for i, chunk_data in enumerate(chunks_with_meta):
            chunk_id = f"{document_id}-{i}"
            chunk_meta = {
                "document_id": document_id,
                "filename": filename,
                "original_filename": filename,
                **doc_metadata,
                # Chunk-level metadata overrides doc-level where relevant
                **chunk_data["metadata"],
            }
            ids.append(chunk_id)
            texts.append(chunk_data["content"])
            metadatas.append(chunk_meta)

        # Batch upsert to ChromaDB
        BATCH = 256  # avoid single huge batch on large PDFs
        for batch_start in range(0, len(ids), BATCH):
            batch_end = batch_start + BATCH
            vector_store.add_documents(
                texts=texts[batch_start:batch_end],
                metadatas=metadatas[batch_start:batch_end],
                ids=ids[batch_start:batch_end],
            )
        logger.info(f"Indexed {chunk_count} chunks for {filename} (doc_id={document_id})")

        # ── Step 8: Persist chunks to PostgreSQL ───────────────────────────────
        for i, chunk_data in enumerate(chunks_with_meta):
            db.add(DocumentChunk(
                document_id=document_id,
                chunk_text=chunk_data["content"],
                metadata_json=json.dumps(metadatas[i]),
                embedding_id=ids[i],
            ))

        document.status = "processed"
        db.commit()

        AuditService.create_entry(
            db, user_id, "upload_document", "documents",
            f"Processed '{filename}': {page_count} pages, {chunk_count} chunks, "
            f"{len(doc_entities.get('officers', []))} officers detected",
        )
        logger.info(f"Document '{filename}' fully processed (doc_id={document_id})")

    except Exception as e:
        logger.error(f"Processing error for '{filename}' (doc_id={document_id}): {e}", exc_info=True)
        if document:
            document.status = "error"
            db.commit()
    finally:
        db.close()


# ── Upload Endpoints ────────────────────────────────────────────────────────────

@router.post("/files", response_model=MultiUploadResponse)
async def upload_files(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    category: str = Form(...),
    source: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Super Admin", "Commanding Officer", "Instructor")),
):
    """
    Upload up to MAX_SIMULTANEOUS_DOCS documents simultaneously.
    Each file is processed asynchronously in a background task.
    Returns immediately with processing status; poll /documents/{id} for completion.
    """
    if len(files) > MAX_SIMULTANEOUS_DOCS:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {MAX_SIMULTANEOUS_DOCS} files per upload batch.",
        )

    results: List[FileStatus] = []
    for file in files:
        filename = Path(file.filename).name
        if not filename.lower().endswith((".xlsx", ".xls", ".csv", ".pdf", ".docx")):
            results.append(FileStatus(
                filename=filename,
                status="error",
                error="Unsupported file type. Accepted: PDF, DOCX, XLSX, XLS, CSV",
            ))
            continue

        try:
            document = Document(
                filename=filename,
                source=source,
                category=category,
                uploader_id=current_user.id,
                status="processing",
            )
            db.add(document)
            db.commit()
            db.refresh(document)

            content = await file.read()
            background_tasks.add_task(
                process_document_task,
                document.id,
                content,
                filename,
                category,
                source,
                current_user.id,
            )
            results.append(FileStatus(
                filename=filename,
                status="processing",
                document_id=document.id,
            ))
            logger.info(f"Queued '{filename}' for processing (doc_id={document.id})")

        except Exception as e:
            logger.error(f"Upload failed for '{filename}': {e}")
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
    """Single-file upload endpoint (backward-compatible)."""
    res = await upload_files(background_tasks, [file], category, source, db, current_user)
    file_res = res.files[0]
    if file_res.status == "error":
        raise HTTPException(status_code=400, detail=file_res.error)
    return DocumentUploadResponse(
        id=file_res.document_id,
        filename=file_res.filename,
        category=category,
        source=source,
        status="processing",
        uploaded_at=datetime.utcnow(),
    )