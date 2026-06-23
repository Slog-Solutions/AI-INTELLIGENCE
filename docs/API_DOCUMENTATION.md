# ATIP Architecture and API Documentation

## System Architecture

### Frontend (React + TypeScript)
- **Framework**: React 19, Vite
- **Auth**: JWT token-based
- **State**: Zustand
- **HTTP**: Axios with interceptors
- **UI**: TailwindCSS

**Pages**:
- Login: Authentication entry point
- Dashboard: Main control center with role-aware navigation
- Upload Center: Document ingestion interface
- Documents: Browse uploaded documents
- AI Assistant: RAG chat interface
- 404: Not found fallback

**Protected Routes**: All pages except login require valid JWT token.

### Backend (FastAPI)
- **Framework**: FastAPI with async support
- **Database**: PostgreSQL with SQLAlchemy ORM
- **Auth**: JWT + HTTPBearer + Role-based access control (RBAC)
- **Vector Store**: ChromaDB with local sentence-transformers embeddings
- **LLM**: Ollama integration for local inference

**API Routes**:
- `/auth` - Login, refresh token, get profile
- `/upload` - Document upload with RBAC
- `/chat` - RAG query interface
- `/documents` - List documents
- `/users` - User management (Admin only)

### Database Schema
- **users**: User accounts with role assignment
- **roles**: Role definitions (Super Admin, CO, Instructor, Analyst)
- **departments**: Military departments
- **units**: Company/unit assignments
- **documents**: Uploaded file metadata
- **document_chunks**: Vectorized text chunks
- **audit_logs**: Action tracking

### Vector Store
- **Storage**: ChromaDB persisted in `vector_store/`
- **Embeddings**: Sentence Transformers (all-MiniLM-L6-v2)
- **Chunks**: Auto-generated from uploaded documents

### LLM Integration
- **Service**: Ollama (local inference server)
- **Default Model**: Qwen3 8B
- **Fallback**: Llama 3 supported
- **No Cloud**: 100% offline operation

## API Documentation

### Authentication Endpoints

#### POST /auth/login
```json
Request:
{
  "username": "admin",
  "password": "Admin123!"
}

Response:
{
  "access_token": "eyJhbGc...",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "username": "admin",
    "email": "admin@atip.local",
    "role": "Super Admin",
    "full_name": "System Admin"
  }
}
```

#### GET /auth/me
Requires: Bearer token
```json
Response: Current user profile
```

#### POST /auth/refresh
Requires: Bearer token
```json
Response:
{
  "access_token": "new-token",
  "token_type": "bearer"
}
```

### Document Endpoints

#### POST /upload/file
Requires: Bearer token, RBAC (not Analyst-only)
```
multipart/form-data:
- file: binary file
- category: string
- source: string

Response:
{
  "id": 1,
  "filename": "report.pdf",
  "category": "War Reports",
  "source": "Field Unit",
  "uploaded_at": "2026-06-17T12:00:00"
}
```

#### GET /documents/list
Requires: Bearer token
```json
Response:
[
  {
    "id": 1,
    "filename": "report.pdf",
    "category": "War Reports",
    "source": "Field Unit",
    "uploaded_at": "2026-06-17T12:00:00"
  }
]
```

### RAG Chat Endpoints

#### POST /chat/query
Requires: Bearer token
```json
Request:
{
  "query": "Summarize the war report"
}

Response:
{
  "answer": "The report describes Operation Eagle conducted...",
  "sources": ["war_report.pdf"]
}
```

### User Management Endpoints

#### GET /users
Requires: Bearer token + Super Admin role
```json
Response: List of all users
```

#### POST /users/create
Requires: Bearer token + Super Admin role
```json
Request:
{
  "username": "new_user",
  "email": "user@atip.local",
  "password": "SecurePass123!",
  "role": "Instructor",
  "full_name": "New Instructor"
}

Response: Created user object
```

## Role-Based Access Control

| Role | Auth | Upload | Chat | Documents | Users |
|------|------|--------|------|-----------|-------|
| Super Admin | ✓ | ✓ | ✓ | ✓ | ✓ |
| Commanding Officer | ✓ | ✓ | ✓ | ✓ | ✗ |
| Instructor | ✓ | ✓ | ✓ | ✓ | ✗ |
| Analyst | ✓ | ✗ | ✓ | ✓ | ✗ |

## Error Handling

All endpoints return standard HTTP status codes:
- `200`: Success
- `201`: Created
- `400`: Bad request
- `401`: Unauthorized (invalid token)
- `403`: Forbidden (insufficient role)
- `404`: Not found
- `500`: Server error

Error responses include detail message:
```json
{
  "detail": "Invalid credentials"
}
```

## Supported Document Formats
- Excel (.xlsx, .xls)
- CSV (.csv)
- PDF (.pdf)
- Word (.docx)

## Security Headers
All responses include CORS headers for local network access.

## Rate Limiting
None implemented (suitable for offline military network).

## Caching
Frontend uses React Query for data caching and stale-while-revalidate patterns.
