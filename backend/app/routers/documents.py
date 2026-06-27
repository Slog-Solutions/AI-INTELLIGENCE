"""
ATIP Documents Router
======================
Endpoints for listing, viewing, deleting and re-indexing documents.

Delete pipeline:
  1. Remove ChromaDB vector entries for the document.
  2. Remove the physical file from the upload directory.
  3. Cascade-delete the PostgreSQL Document record (chunks FK-cascade deleted).

Re-index pipeline (NEW):
  1. Delete existing ChromaDB vectors for the document.
  2. Delete existing DocumentChunk records.
  3. Re-parse the physical file.
  4. Re-chunk, re-embed, re-insert.
  5. Update document metadata and status.

VectorStore is constructed once per request using the module-level singleton
model — no model reload occurs.
"""

import io
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..config import UPLOAD_DIR, CHUNK_SIZE, CHUNK_OVERLAP
from ..core.rbac import require_roles
from ..db.session import SessionLocal
from ..models import Document, DocumentChunk, Unit, User
from ..schemas import DocumentOut, DocumentReindexResponse
from ..services.analytics_service import AnalyticsService
from ..services.document_processor import DocumentProcessor
from ..services.rag_engine import RAGEngine
from ..services.vectorstore import VectorStore

logger = logging.getLogger(__name__)
router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── List ───────────────────────────────────────────────────────────────────────

@router.get("/list", response_model=List[DocumentOut])
def list_documents(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(
        "Super Admin", "Commanding Officer", "Instructor", "Analyst"
    )),
):
    docs = db.query(Document).order_by(Document.uploaded_at.desc()).all()
    result: List[DocumentOut] = []
    for doc in docs:
        metadata  = json.loads(doc.metadata_json)  if doc.metadata_json  else {}
        preview   = json.loads(doc.preview_json)   if doc.preview_json   else None
        analytics = json.loads(doc.analytics_json) if doc.analytics_json else None
        # Strip large entity blobs for list view (keep entity counts)
        metadata_clean = {k: v for k, v in metadata.items() if k != "entities"}
        if "entities" in metadata:
            metadata_clean["entity_counts"] = {
                k: len(v) for k, v in metadata["entities"].items() if isinstance(v, list)
            }
        result.append(DocumentOut(
            id=doc.id,
            filename=doc.filename,
            category=doc.category,
            source=doc.source,
            status=doc.status,
            summary=doc.summary,
            preview=preview,
            metadata=metadata_clean,
            analytics=analytics,
            page_count=doc.page_count,
            chunk_count=doc.chunk_count,
            uploaded_at=doc.uploaded_at,
        ))
    return result


# ── Single document ────────────────────────────────────────────────────────────

@router.get("/{document_id}", response_model=DocumentOut)
def get_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(
        "Super Admin", "Commanding Officer", "Instructor", "Analyst"
    )),
):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    metadata  = json.loads(doc.metadata_json)  if doc.metadata_json  else {}
    preview   = json.loads(doc.preview_json)   if doc.preview_json   else None
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
        page_count=doc.page_count,
        chunk_count=doc.chunk_count,
        uploaded_at=doc.uploaded_at,
    )


# ── Delete ─────────────────────────────────────────────────────────────────────

@router.delete("/{document_id}")
def delete_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Super Admin", "Commanding Officer")),
):
    """
    Delete a document completely:
      1. Remove embeddings from ChromaDB (uses singleton model — no reload).
      2. Remove the physical file from disk.
      3. Cascade-delete PostgreSQL records (DocumentChunk FK-cascade deleted).
    """
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    filename = doc.filename

    try:
        # ── Step 1: Remove Chroma vectors ──────────────────────────────────
        try:
            vector_store = VectorStore()
            chunks = (
                db.query(DocumentChunk)
                .filter(DocumentChunk.document_id == document_id)
                .all()
            )
            chunk_ids = [c.embedding_id for c in chunks if c.embedding_id]
            if chunk_ids:
                vector_store.delete_by_ids(chunk_ids)
                logger.info(
                    f"Deleted {len(chunk_ids)} Chroma vectors for "
                    f"doc_id={document_id} ('{filename}')"
                )
            else:
                logger.warning(
                    f"No Chroma vector IDs found for doc_id={document_id}; "
                    "skipping vector deletion"
                )
        except Exception as vec_exc:
            logger.error(
                f"Vector deletion failed for doc_id={document_id}: {vec_exc}",
                exc_info=True,
            )

        # ── Step 2: Remove physical file ───────────────────────────────────
        saved_filename = filename
        if doc.metadata_json:
            try:
                meta = json.loads(doc.metadata_json)
                saved_filename = meta.get("saved_filename", filename)
            except Exception:
                pass

        file_path = Path(UPLOAD_DIR) / saved_filename
        if file_path.exists():
            try:
                file_path.unlink()
                logger.info(f"Deleted file '{file_path}'")
            except Exception as file_exc:
                logger.warning(f"Could not delete file '{file_path}': {file_exc}")
        else:
            logger.warning(f"Physical file not found at '{file_path}'; skipping file deletion")

        # ── Step 3: Delete PostgreSQL record (cascades to chunks) ──────────
        db.delete(doc)
        db.commit()
        logger.info(f"Deleted document '{filename}' (doc_id={document_id}) from DB")

        return {"message": f"Document '{filename}' deleted successfully"}

    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        logger.error(f"Delete failed for doc_id={document_id}: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Delete failed: {str(exc)}")


# ── Re-index ───────────────────────────────────────────────────────────────────

def _reindex_document_task(document_id: int, user_id: int):
    """
    Background task: delete existing vectors + chunks, re-parse file, re-embed, re-insert.
    """
    db = SessionLocal()
    document = None
    try:
        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            logger.error(f"Re-index: Document ID {document_id} not found")
            return

        document.status = "processing"
        db.commit()

        # Resolve physical file path
        saved_filename = document.filename
        if document.metadata_json:
            try:
                meta = json.loads(document.metadata_json)
                saved_filename = meta.get("saved_filename", document.filename)
            except Exception:
                pass

        file_path = Path(UPLOAD_DIR) / saved_filename
        if not file_path.exists():
            logger.error(f"Re-index: File not found at {file_path}")
            document.status = "error"
            db.commit()
            return

        # ── 1. Remove old Chroma vectors ───────────────────────────────────
        vector_store = VectorStore()
        old_chunks = db.query(DocumentChunk).filter(DocumentChunk.document_id == document_id).all()
        old_ids = [c.embedding_id for c in old_chunks if c.embedding_id]
        if old_ids:
            vector_store.delete_by_ids(old_ids)

        # ── 2. Delete old chunk records ────────────────────────────────────
        db.query(DocumentChunk).filter(DocumentChunk.document_id == document_id).delete()
        db.commit()

        # ── 3. Re-parse ────────────────────────────────────────────────────
        ext = document.filename.lower()
        parsed_content: dict = {}
        if ext.endswith((".xlsx", ".xls")):
            parsed_content = DocumentProcessor.parse_excel(str(file_path))
        elif ext.endswith(".csv"):
            parsed_content = DocumentProcessor.parse_csv(str(file_path))
        elif ext.endswith(".pdf"):
            parsed_content = DocumentProcessor.parse_pdf(str(file_path))
        elif ext.endswith(".docx"):
            parsed_content = DocumentProcessor.parse_docx(str(file_path))
        elif ext.endswith(".txt"):
            parsed_content = DocumentProcessor.parse_txt(str(file_path))
        else:
            document.status = "error"
            db.commit()
            return

        if parsed_content.get("error"):
            document.status = "error"
            db.commit()
            return

        # ── 4. Re-chunk ────────────────────────────────────────────────────
        chunks_with_meta = DocumentProcessor.to_chunks(
            parsed_content,
            document.filename,
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
        )
        if not chunks_with_meta:
            document.status = "error"
            db.commit()
            return

        full_text = parsed_content.get("full_text", "")
        doc_entities = DocumentProcessor.extract_entities(full_text[:20000])
        page_count = parsed_content.get("page_count", 0)
        chunk_count = len(chunks_with_meta)

        doc_metadata = DocumentProcessor.extract_metadata(
            str(file_path), document.filename,
            document.category, document.source,
            page_count, chunk_count, doc_entities,
        )
        document.metadata_json = json.dumps(doc_metadata)
        document.page_count = page_count
        document.chunk_count = chunk_count
        document.preview_json = json.dumps(DocumentProcessor.generate_preview(parsed_content))

        analytics = AnalyticsService.generate_analytics(str(file_path), document.filename, parsed_content)
        document.analytics_json = json.dumps(analytics)

        # ── 5. Re-embed ────────────────────────────────────────────────────
        rag = RAGEngine(vector_store)
        try:
            summary_context = " ".join([c["content"] for c in chunks_with_meta[:5]])
            document.summary = rag.summarize_document(document.filename, summary_context)
        except Exception as e:
            logger.warning(f"Summary failed during re-index: {e}")

        ids: List[str] = []
        texts: List[str] = []
        metadatas: List[dict] = []

        for i, chunk_data in enumerate(chunks_with_meta):
            chunk_id = f"{document_id}-{i}"
            chunk_meta = {
                "document_id": document_id,
                "filename": document.filename,
                "original_filename": document.filename,
                **doc_metadata,
                **chunk_data["metadata"],
            }
            ids.append(chunk_id)
            texts.append(chunk_data["content"])
            metadatas.append(chunk_meta)

        BATCH = 256
        for batch_start in range(0, len(ids), BATCH):
            batch_end = batch_start + BATCH
            vector_store.add_documents(
                texts=texts[batch_start:batch_end],
                metadatas=metadatas[batch_start:batch_end],
                ids=ids[batch_start:batch_end],
            )

        # ── 6. Re-insert chunks ────────────────────────────────────────────
        for i, chunk_data in enumerate(chunks_with_meta):
            db.add(DocumentChunk(
                document_id=document_id,
                chunk_text=chunk_data["content"],
                metadata_json=json.dumps(metadatas[i]),
                embedding_id=ids[i],
            ))

        document.status = "processed"
        db.commit()
        logger.info(f"Re-indexed '{document.filename}' (doc_id={document_id}): {chunk_count} chunks")

    except Exception as e:
        logger.error(f"Re-index error for doc_id={document_id}: {e}", exc_info=True)
        if document:
            document.status = "error"
            db.commit()
    finally:
        db.close()


@router.post("/{document_id}/reindex", response_model=DocumentReindexResponse)
def reindex_document(
    document_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Super Admin", "Commanding Officer")),
):
    """
    Queue a document for re-indexing.
    Useful after changing embedding model or fixing a corrupted index.
    Returns immediately; processing runs in the background.
    """
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    doc.status = "processing"
    db.commit()

    background_tasks.add_task(_reindex_document_task, document_id, current_user.id)

    return DocumentReindexResponse(
        document_id=document_id,
        status="processing",
        message=f"Re-indexing '{doc.filename}' has been queued.",
    )


# ── Stats ──────────────────────────────────────────────────────────────────────

@router.get("/stats")
def get_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(
        "Super Admin", "Commanding Officer", "Instructor", "Analyst"
    )),
):
    doc_count        = db.query(func.count(Document.id)).scalar()
    unit_count       = db.query(func.count(Unit.id)).scalar()
    error_count      = db.query(func.count(Document.id)).filter(Document.status == "error").scalar()
    processing_count = db.query(func.count(Document.id)).filter(Document.status == "processing").scalar()

    categories_raw = (
        db.query(Document.category, func.count(Document.id))
        .group_by(Document.category)
        .all()
    )
    categories = [{"name": c[0], "value": c[1]} for c in categories_raw]

    recent_uploads = (
        db.query(Document)
        .order_by(Document.uploaded_at.desc())
        .limit(5)
        .all()
    )

    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    trends_raw = (
        db.query(
            func.date(Document.uploaded_at).label("date"),
            func.count(Document.id).label("count"),
        )
        .filter(Document.uploaded_at >= seven_days_ago)
        .group_by(func.date(Document.uploaded_at))
        .all()
    )
    upload_trends = [{"date": str(t[0]), "uploads": t[1]} for t in trends_raw]

    # Aggregate entities and keywords from analytics / metadata JSON
    all_risks:    List[str] = []
    all_keywords: dict      = {}
    all_entities: dict      = {}

    docs_with_data = db.query(Document).filter(
        (Document.analytics_json.isnot(None)) | (Document.metadata_json.isnot(None))
    ).all()

    for doc in docs_with_data:
        if doc.analytics_json:
            try:
                ad = json.loads(doc.analytics_json)
                for r in ad.get("risks", []):
                    all_risks.append(r)
                for kw in ad.get("keywords", []):
                    all_keywords[kw] = all_keywords.get(kw, 0) + 1
            except Exception:
                pass

        if doc.metadata_json:
            try:
                meta = json.loads(doc.metadata_json)
                for ent_type, ent_list in meta.get("entities", {}).items():
                    if isinstance(ent_list, list):
                        all_entities.setdefault(ent_type, [])
                        all_entities[ent_type].extend(ent_list)
            except Exception:
                pass

    deduped_entities = {
        k: list(dict.fromkeys(v))[:20] for k, v in all_entities.items()
    }
    keyword_frequency = [
        {"name": k, "value": v}
        for k, v in sorted(
            all_keywords.items(), key=lambda x: x[1], reverse=True
        )[:10]
    ]

    # Entity frequency charts — top officers and units
    officer_frequency = [
        {"name": o, "value": 1}
        for o in deduped_entities.get("officers", [])[:10]
    ]
    unit_frequency = [
        {"name": u, "value": 1}
        for u in deduped_entities.get("units", [])[:10]
    ]

    # Total Chroma vectors
    total_vectors = 0
    try:
        vs = VectorStore()
        total_vectors = vs.count()
    except Exception as exc:
        logger.warning(f"Could not fetch vector count from Chroma: {exc}")

    return {
        "documents_processed":  doc_count,
        "active_units":         unit_count,
        "ai_alerts":            error_count      or 0,
        "processing_queue":     processing_count or 0,
        "total_vectors_indexed": total_vectors,
        "categories":           categories,
        "detected_entities":    deduped_entities,
        "recent_uploads": [
            {
                "id":          d.id,
                "filename":    d.filename,
                "uploaded_at": d.uploaded_at,
                "status":      d.status,
                "page_count":  d.page_count,
                "chunk_count": d.chunk_count,
                "category":    d.category,
            }
            for d in recent_uploads
        ],
        "analytics": {
            "upload_trends":    upload_trends,
            "risk_indicators":  [{"label": r, "level": "Medium"} for r in all_risks[:5]],
            "keyword_frequency": keyword_frequency,
            "officer_frequency": officer_frequency,
            "unit_frequency":    unit_frequency,
            "document_insights": (
                f"Indexed {total_vectors} chunks across {doc_count} documents. "
                f"Detected "
                f"{len(deduped_entities.get('officers', []))} officers, "
                f"{len(deduped_entities.get('units', []))} units, "
                f"{len(deduped_entities.get('operations', []))} operations."
            ),
        },
    }