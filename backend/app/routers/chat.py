from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from ..db.session import SessionLocal
from ..models import Document, DocumentChunk, User, Conversation, Message
from ..services.vectorstore import VectorStore
from ..services.rag_engine import RAGEngine
from ..services.audit_service import AuditService
from ..services.document_processor import DocumentProcessor
from ..schemas import ChatRequest, ChatResponse, SourceCitation, ConversationOut, ConversationCreate
from ..core.dependencies import get_current_user
from ..core.rbac import require_roles
from typing import List, Optional
import re
import json
import io
import uuid

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/query", response_model=ChatResponse)
def query_chat(request: ChatRequest, db: Session = Depends(get_db), current_user: User = Depends(require_roles("Super Admin", "Commanding Officer", "Instructor", "Analyst"))):
    vector_store = VectorStore()
    rag = RAGEngine(vector_store)
    try:
        # Handle conversation history if provided
        history = ""
        conv_id = request.conversation_id
        if conv_id:
            conv = db.query(Conversation).filter(Conversation.id == conv_id, Conversation.user_id == current_user.id).first()
            if conv:
                # Get last 5 messages for context
                msgs = db.query(Message).filter(Message.conversation_id == conv_id).order_by(Message.created_at.desc()).limit(5).all()
                history = "\n".join([f"{m.role}: {m.content}" for m in reversed(msgs)])

        full_query = f"{history}\nuser: {request.query}" if history else request.query
        response = rag.query(full_query)
        
        confidence_match = re.search(r"Confidence: (High|Medium|Low)", response["answer"])
        confidence = confidence_match.group(1) if confidence_match else None
        if confidence_match:
            response["answer"] = response["answer"].replace(confidence_match.group(0), "").strip()

        structured_sources: List[SourceCitation] = []
        for src_str in response["sources"]:
            match = re.match(r"(.*?)(?: \(Page (\d+)\))?", src_str)
            if match:
                filename = match.group(1).strip()
                page_number = int(match.group(2)) if match.group(2) else None
                structured_sources.append(SourceCitation(filename=filename, page_number=page_number))
            else:
                structured_sources.append(SourceCitation(filename=src_str))

        # Save to database if conversation exists
        if not conv_id:
            # Create a new conversation if none exists
            new_conv = Conversation(title=request.query[:50], user_id=current_user.id)
            db.add(new_conv)
            db.commit()
            db.refresh(new_conv)
            conv_id = new_conv.id

        # Save user message
        db.add(Message(conversation_id=conv_id, role="user", content=request.query))
        # Save assistant message
        db.add(Message(
            conversation_id=conv_id, 
            role="assistant", 
            content=response["answer"],
            sources_json=json.dumps([s.model_dump() for s in structured_sources])
        ))
        db.commit()

        AuditService.create_entry(db, current_user.id, "chat_query", "chat", f"Query: {request.query}")

        return ChatResponse(
            answer=response["answer"], 
            sources=structured_sources,
            confidence=confidence,
            conversation_id=conv_id
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@router.post("/query-with-file", response_model=ChatResponse)
async def query_with_file(
    query: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Super Admin", "Commanding Officer", "Instructor", "Analyst"))
):
    try:
        content = await file.read()
        filename = file.filename
        file_obj = io.BytesIO(content)
        
        # Temporary processing (no DB storage)
        saved_path = DocumentProcessor.save_upload(file_obj, f"temp_{uuid.uuid4()}_{filename}")
        
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
            raise HTTPException(status_code=422, detail=parsed_content["error"])

        chunks = DocumentProcessor.to_chunks(parsed_content, filename)
        
        # Create temporary vector store/collection for this request
        temp_vector_store = VectorStore() 
        temp_ids = [f"temp-{uuid.uuid4()}-{i}" for i in range(len(chunks))]
        temp_texts = [c["content"] for c in chunks]
        temp_metadatas = [{"filename": filename, "is_temp": True} for _ in chunks]
        
        temp_vector_store.add_documents(texts=temp_texts, metadatas=temp_metadatas, ids=temp_ids)
        
        rag = RAGEngine(temp_vector_store)
        response = rag.query(query)
        
        structured_sources = [SourceCitation(filename=filename)]
        
        return ChatResponse(
            answer=response["answer"],
            sources=structured_sources,
            confidence="High"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/conversation", response_model=ConversationOut)
def create_conversation(req: ConversationCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    conv = Conversation(title=req.title, user_id=current_user.id)
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv

@router.get("/conversations", response_model=List[ConversationOut])
def get_conversations(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(Conversation).filter(Conversation.user_id == current_user.id).order_by(Conversation.updated_at.desc()).all()

@router.get("/conversation/{id}", response_model=ConversationOut)
def get_conversation(id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    conv = db.query(Conversation).filter(Conversation.id == id, Conversation.user_id == current_user.id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    # Map sources_json back to sources list for each message
    for msg in conv.messages:
        if msg.sources_json:
            msg.sources = json.loads(msg.sources_json)
    return conv

@router.delete("/conversation/{id}")
def delete_conversation(id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    conv = db.query(Conversation).filter(Conversation.id == id, Conversation.user_id == current_user.id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    db.delete(conv)
    db.commit()
    return {"status": "deleted"}
