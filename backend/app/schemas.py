from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr
from typing import Optional, List, Any

class TokenPayload(BaseModel):
    sub: str
    exp: int

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class LoginResponse(TokenResponse):
    user: "UserOut"

class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    full_name: Optional[str] = None
    role: str
    department_id: Optional[int] = None
    unit_id: Optional[int] = None

class UserOut(BaseModel):
    id: int
    username: str
    email: EmailStr
    full_name: Optional[str]
    role: str
    department_id: Optional[int]
    unit_id: Optional[int]
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class LoginRequest(BaseModel):
    username: str
    password: str

class DocumentUploadResponse(BaseModel):
    id: int
    filename: str
    category: str
    source: str
    uploaded_at: datetime

class DocumentOut(BaseModel):
    id: int
    filename: str
    category: str
    source: str
    metadata: Optional[str]
    uploaded_at: datetime

class ChatRequest(BaseModel):
    query: str

class ChatResponse(BaseModel):
    answer: str
    sources: List[str] = []
