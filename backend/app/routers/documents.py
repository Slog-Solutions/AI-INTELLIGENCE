"""
ATIP Documents Router
======================
Endpoints for listing, viewing, and deleting indexed documents.

Delete pipeline (fixed):
  1. Remove ChromaDB vector entries for the document.
  2. Remove the physical file from the upload directory.
  3. Cascade-delete the PostgreSQL Document record (chunks FK-cascade deleted).

VectorStore is constructed once per request using the module-level singleton
model — no model reload occurs.
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..config import UPLOAD_DIR
from ..core.rbac import require_roles
from ..db.session import SessionLocal
from ..models import Document, DocumentChunk, Unit, User
from ..schemas import DocumentOut
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
        # Strip large entity blobs for list view
        metadata_clean = {k: v for k, v in metadata.items() if k != "entities"}
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

    filename = doc.filename  # capture before deletion

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
            # Log but do not abort — proceed to DB and file cleanup.
            logger.error(
                f"Vector deletion failed for doc_id={document_id}: {vec_exc}",
                exc_info=True,
            )

        # ── Step 2: Remove physical file ───────────────────────────────────
        # Resolve the saved filename from metadata if available, else use
        # the stored filename directly.
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
                logger.warning(
                    f"Could not delete file '{file_path}': {file_exc}"
                )
        else:
            logger.warning(
                f"Physical file not found at '{file_path}'; "
                "skipping file deletion"
            )

        # ── Step 3: Delete PostgreSQL record (cascades to chunks) ──────────
        db.delete(doc)
        db.commit()
        logger.info(f"Deleted document '{filename}' (doc_id={document_id}) from DB")

        return {"message": f"Document '{filename}' deleted successfully"}

    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        logger.error(
            f"Delete failed for doc_id={document_id}: {exc}",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=f"Delete failed: {str(exc)}")


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

    docs_with_data = (
        db.query(Document).filter(Document.analytics_json.isnot(None)).all()
    )
    for doc in docs_with_data:
        try:
            ad = json.loads(doc.analytics_json)
            for r in ad.get("risks", []):
                all_risks.append(r)
            for kw in ad.get("keywords", []):
                all_keywords[kw] = all_keywords.get(kw, 0) + 1
        except Exception:
            pass

        try:
            if doc.metadata_json:
                meta = json.loads(doc.metadata_json)
                for ent_type, ent_list in meta.get("entities", {}).items():
                    if isinstance(ent_list, list):
                        all_entities.setdefault(ent_type, [])
                        all_entities[ent_type].extend(ent_list)
        except Exception:
            pass

    deduped_entities = {
        k: list(dict.fromkeys(v))[:10] for k, v in all_entities.items()
    }
    keyword_frequency = [
        {"name": k, "value": v}
        for k, v in sorted(
            all_keywords.items(), key=lambda x: x[1], reverse=True
        )[:10]
    ]

    # Total Chroma vectors — use singleton, no model reload
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
            }
            for d in recent_uploads
        ],
        "analytics": {
            "upload_trends":    upload_trends,
            "risk_indicators":  [{"label": r, "level": "Medium"} for r in all_risks[:5]],
            "keyword_frequency": keyword_frequency,
            "document_insights": (
                f"Indexed {total_vectors} chunks across {doc_count} documents. "
                f"Detected "
                f"{len(deduped_entities.get('officers', []))} officers, "
                f"{len(deduped_entities.get('units', []))} units, "
                f"{len(deduped_entities.get('operations', []))} operations."
            ),
        },
    }