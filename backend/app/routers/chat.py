"""
ATIP Chat Router
=================
Query endpoints powered by the enterprise RAG engine:
  - /chat/query            — standard RAG query (searches ALL indexed documents)
  - /chat/query-with-file  — ad-hoc query against a single uploaded file
  - /chat/conversation*    — conversation CRUD with persistent message history

Every response carries:
  - answer       — LLM-generated answer anchored to retrieved context
  - sources      — list of {filename, page_number, section} citations
  - confidence   — HIGH | MEDIUM | LOW
  - thought      — internal chain-of-thought (if model supports it)
  - conversation_id
"""

import io
import json
import logging
import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List, Optional

from ..db.session import SessionLocal
from ..models import Document, DocumentChunk, User, Conversation, Message
from ..services.vectorstore import VectorStore
from ..services.rag_engine import RAGEngine
from ..services.audit_service import AuditService
from ..services.document_processor import DocumentProcessor
from ..schemas import (
    ChatRequest, ChatResponse, SourceCitation,
    ConversationOut, ConversationCreate,
)
from ..core.dependencies import get_current_user
from ..core.rbac import require_roles
from ..config import RAG_RETRIEVE_TOP_K, RAG_RERANK_TOP_K, RAG_MAX_CONTEXT_TOKENS

logger = logging.getLogger(__name__)
router = APIRouter()

# ── DB Dependency ──────────────────────────────────────────────────────────────
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Shared helpers ─────────────────────────────────────────────────────────────
def _parse_source_citations(source_strings: List[str]) -> List[SourceCitation]:
    """
    Convert source strings like "report.pdf (Page 5) [Section 2]"
    into structured SourceCitation objects.
    """
    citations: List[SourceCitation] = []
    for src in source_strings:
        # Extract page number
        page_match = re.search(r'\(Page\s+(\d+)\)', src, re.IGNORECASE)
        page_num = int(page_match.group(1)) if page_match else None

        # Extract section
        sec_match = re.search(r'\[(.+?)\]', src)
        section = sec_match.group(1).strip() if sec_match else None

        # Clean filename
        filename = src
        if page_match:
            filename = filename[:page_match.start()].strip()
        if sec_match:
            filename = filename[:sec_match.start()].strip()
        filename = filename.strip("() ")

        citations.append(SourceCitation(
            filename=filename,
            page_number=page_num,
            section=section,
        ))
    return citations


def _build_history_string(db: Session, conv_id: int, limit: int = 6) -> str:
    """Retrieve last `limit` messages from a conversation for context."""
    msgs = (
        db.query(Message)
        .filter(Message.conversation_id == conv_id)
        .order_by(Message.created_at.desc())
        .limit(limit)
        .all()
    )
    if not msgs:
        return ""
    lines = []
    for m in reversed(msgs):
        role = "User" if m.role == "user" else "Assistant"
        lines.append(f"{role}: {m.content}")
    return "\n".join(lines)


# ── /chat/query ────────────────────────────────────────────────────────────────
@router.post("/query", response_model=ChatResponse)
def query_chat(
    request: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(
        "Super Admin", "Commanding Officer", "Instructor", "Analyst"
    )),
):
    """
    Main RAG query endpoint.
    Searches ALL indexed documents with hybrid retrieval (semantic + BM25 + entity).
    Applies FlashRank reranking, then sends top 8–12 chunks to the LLM.
    """
    vector_store = VectorStore()
    rag = RAGEngine(
        vector_store,
        top_k_retrieve=RAG_RETRIEVE_TOP_K,
        top_k_rerank=RAG_RERANK_TOP_K,
        max_context_tokens=RAG_MAX_CONTEXT_TOKENS,
    )

    # ── Build conversation history ──────────────────────────────────────────────
    history = ""
    conv_id = request.conversation_id
    if conv_id:
        conv = db.query(Conversation).filter(
            Conversation.id == conv_id,
            Conversation.user_id == current_user.id,
        ).first()
        if conv:
            history = _build_history_string(db, conv_id)

    try:
        response = rag.query(
            query=request.query,
            history=history,
        )
    except Exception as exc:
        logger.error(f"RAG query exception: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))

    # ── Parse structured citations ─────────────────────────────────────────────
    structured_sources = _parse_source_citations(response.get("sources", []))

    # ── Persist conversation ───────────────────────────────────────────────────
    if not conv_id:
        new_conv = Conversation(
            title=request.query[:80],
            user_id=current_user.id,
        )
        db.add(new_conv)
        db.commit()
        db.refresh(new_conv)
        conv_id = new_conv.id

    db.add(Message(
        conversation_id=conv_id,
        role="user",
        content=request.query,
    ))
    db.add(Message(
        conversation_id=conv_id,
        role="assistant",
        content=response["answer"],
        sources_json=json.dumps([s.model_dump() for s in structured_sources]),
    ))
    db.commit()

    AuditService.create_entry(
        db, current_user.id, "chat_query", "chat",
        f"Query: {request.query[:120]}",
    )

    return ChatResponse(
        answer=response["answer"],
        sources=structured_sources,
        confidence=response.get("confidence"),
        thought=response.get("thought"),
        conversation_id=conv_id,
    )


# ── /chat/query-with-file ─────────────────────────────────────────────────────
@router.post("/query-with-file", response_model=ChatResponse)
async def query_with_file(
    query: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(
        "Super Admin", "Commanding Officer", "Instructor", "Analyst"
    )),
):
    """
    Ad-hoc query against a single uploaded file (not persisted to the main index).
    Uses a temporary ChromaDB collection scoped to this request.
    """
    from ..services.vectorstore import VectorStore as VS

    content = await file.read()
    filename = file.filename
    ext = filename.lower()

    # Save to temp path
    temp_name = f"temp_{uuid.uuid4().hex}_{filename}"
    file_obj = io.BytesIO(content)
    saved_path = DocumentProcessor.save_upload(file_obj, temp_name)

    # Parse
    parsed: dict = {}
    if ext.endswith((".xlsx", ".xls")):
        parsed = DocumentProcessor.parse_excel(saved_path)
    elif ext.endswith(".csv"):
        parsed = DocumentProcessor.parse_csv(saved_path)
    elif ext.endswith(".pdf"):
        parsed = DocumentProcessor.parse_pdf(saved_path)
    elif ext.endswith(".docx"):
        parsed = DocumentProcessor.parse_docx(saved_path)
    else:
        raise HTTPException(status_code=400, detail="Unsupported file type")

    if parsed.get("error"):
        raise HTTPException(status_code=422, detail=parsed["error"])

    chunks = DocumentProcessor.to_chunks(parsed, filename)
    if not chunks:
        raise HTTPException(status_code=422, detail="No content could be extracted from the file")

    # Use a scoped temporary collection name
    temp_collection = f"atip_temp_{uuid.uuid4().hex[:12]}"
    temp_vs = VS(collection_name=temp_collection)
    temp_ids = [f"t-{i}" for i in range(len(chunks))]
    temp_texts = [c["content"] for c in chunks]
    temp_metas = [
        {**c["metadata"], "filename": filename, "original_filename": filename}
        for c in chunks
    ]
    temp_vs.add_documents(texts=temp_texts, metadatas=temp_metas, ids=temp_ids)

    rag = RAGEngine(
        temp_vs,
        top_k_retrieve=min(30, len(chunks)),
        top_k_rerank=8,
        max_context_tokens=4000,
    )

    try:
        response = rag.query(query=query)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    # Cleanup temp collection
    try:
        temp_vs.client.delete_collection(temp_collection)
    except Exception:
        pass

    structured_sources = _parse_source_citations(response.get("sources", []))

    return ChatResponse(
        answer=response["answer"],
        sources=structured_sources,
        confidence=response.get("confidence"),
        thought=response.get("thought"),
    )


# ── Conversation CRUD ──────────────────────────────────────────────────────────

@router.post("/conversation", response_model=ConversationOut)
def create_conversation(
    req: ConversationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    conv = Conversation(title=req.title, user_id=current_user.id)
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv


@router.get("/conversations", response_model=List[ConversationOut])
def get_conversations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return (
        db.query(Conversation)
        .filter(Conversation.user_id == current_user.id)
        .order_by(Conversation.updated_at.desc())
        .all()
    )


@router.get("/conversation/{id}", response_model=ConversationOut)
def get_conversation(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    conv = db.query(Conversation).filter(
        Conversation.id == id,
        Conversation.user_id == current_user.id,
    ).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Hydrate sources
    for msg in conv.messages:
        if msg.sources_json:
            try:
                msg.sources = json.loads(msg.sources_json)
            except Exception:
                msg.sources = []
    return conv


@router.delete("/conversation/{id}")
def delete_conversation(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    conv = db.query(Conversation).filter(
        Conversation.id == id,
        Conversation.user_id == current_user.id,
    ).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    db.delete(conv)
    db.commit()
    return {"status": "deleted"}