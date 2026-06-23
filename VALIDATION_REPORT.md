# Phase 1 Validation Report

Date: 2026-06-17

Scope: Complete Phase 1 validation before Phase 2. This report records command evidence and implementation findings. Result: Phase 1 is not validated as complete. Phase 2 should not start until the blocking failures below are fixed and re-tested.

## Environment Evidence

| Check | Evidence | Result |
| --- | --- | --- |
| Python | `python --version` -> `Python 3.13.7` | Available |
| Node | `node --version` -> `v22.18.0` | Available |
| npm | `npm.cmd --version` -> `11.5.2`; plain `npm` is blocked by PowerShell execution policy | Available through `npm.cmd` |
| Docker | `docker --version` -> command not found | Not available |
| PostgreSQL port | `Test-NetConnection localhost -Port 5432` timed out / connection failed | Not running locally |
| `psql` client | `psql --version` -> command not found | Not installed or not on PATH |
| Ollama | `ollama --version` -> command not found; port `11434` connection failed | Not running locally |
| Backend dependency install | `.venv-validation\Scripts\python.exe -m pip install -r backend\requirements.txt` -> no matching distribution for `passlib==1.7.5` | Fails |
| Frontend dependency install | `npm.cmd install` -> no matching version for `@types/react-router-dom@^6.18.2` | Fails |

## Backend Startup

Command:

```powershell
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

Result: Failed before FastAPI could start.

Primary error:

```text
ImportError: email-validator is not installed, run `pip install pydantic[email]`
```

Additional backend runtime issue:

```text
PermissionError: [WinError 5] Access is denied: 'E:\SLOG PROJECTS\uploads'
```

Cause: `backend/app/config.py` computes `UPLOAD_DIR` and `VECTOR_DIR` as `BASE_DIR.parent.parent / "uploads"` and `BASE_DIR.parent.parent / "vector_store"`. With the current structure, that points outside the project root. The repository already contains `uploads/` and `vector_store/` inside `AI INTELLIGENCE/`.

Status: Backend does not start successfully.

## Registered Route List

Static route registration from `backend/app/main.py` and router files:

| Method | Path | Auth/RBAC |
| --- | --- | --- |
| GET | `/` | Public |
| POST | `/auth/login` | Public |
| POST | `/auth/refresh` | Authenticated user |
| GET | `/auth/me` | Authenticated user |
| POST | `/auth/register` | Authenticated, Super Admin checked inside handler |
| POST | `/upload/file` | Super Admin, Commanding Officer, Instructor, Analyst |
| POST | `/chat/query` | Super Admin, Commanding Officer, Instructor, Analyst |
| GET | `/users/` | Super Admin |
| POST | `/users/create` | Super Admin |
| GET | `/documents/list` | Super Admin, Commanding Officer, Instructor, Analyst |

Note: Because the backend cannot import/start, this list could not be confirmed through FastAPI `/openapi.json`. It is a source-code-derived route list.

## PostgreSQL Integration

Implemented:

- SQLAlchemy engine and session setup exists in `backend/app/db/session.py`.
- ORM models exist in `backend/app/models.py`.
- SQL schema exists in `database/schema.sql`.
- `Base.metadata.create_all(bind=engine)` is called in `backend/app/main.py`.

Failed or blocked:

- PostgreSQL was not reachable on `localhost:5432`.
- `psql` is not available on PATH.
- Backend import/start fails before database validation can run.
- Tables could not be confirmed in a live PostgreSQL database.
- Insert/retrieve test records could not be executed.

Schema relationship intent:

- `units.department_id -> departments.id`
- `users.role_id -> roles.id`
- `users.department_id -> departments.id`
- `users.unit_id -> units.id`
- `documents.uploader_id -> users.id`
- `document_chunks.document_id -> documents.id`

Relationship gaps:

- ORM relationships are incomplete. `User` has `role`, but no `department`, `unit`, `documents`, or `audit_logs` relationships.
- `Document` has no `uploader` or `chunks` relationship.
- `DocumentChunk` has no `document` relationship.
- `AuditLog.user_id` is not declared as a foreign key in the ORM or `schema.sql`.

## Authentication, JWT, and RBAC

Implemented:

- JWT creation and decoding in `backend/app/core/security.py`.
- Password hashing and verification through Passlib bcrypt.
- HTTP Bearer token dependency in `backend/app/core/dependencies.py`.
- Role checks through `require_roles`.
- Login route returns token and user object.

Failed or blocked:

- Login with sample users could not be executed because backend does not start and PostgreSQL is unavailable.
- Token generation via login could not be verified.
- Protected endpoint access could not be verified.
- RBAC restrictions could not be verified by live requests.

Code-level concerns:

- Default `JWT_SECRET_KEY=change-me-secret` is insecure and committed in `backend/.env`.
- Only `admin / Admin123!` is created by `scripts/seed_db.py`. The claimed users `co_alpha`, `instructor_alpha`, and `analyst_main` are documented but not seeded.
- RBAC documentation says Analyst cannot upload, but `backend/app/routers/upload.py` allows `Analyst`.
- Frontend has `RoleRoute`, but `App.tsx` does not use it.

## ChromaDB and Embeddings

Implemented:

- `VectorStore` service exists.
- Collection name is `atip_documents`.
- Intended embedding model is `all-MiniLM-L6-v2`.

Failed:

```powershell
python -c "from backend.app.services.vectorstore import VectorStore; ..."
```

Result:

```text
ModuleNotFoundError: No module named 'chromadb'
```

Additional implementation issue:

- `backend/requirements.txt` uses `chroma-db==0.4.0`, but the import in code is `chromadb`. The commonly used package name is `chromadb`, not `chroma-db`.
- The code passes `embedding_function` into `collection.add()` and `collection.query()`. ChromaDB normally expects the embedding function when creating/getting the collection, not per add/query call. This likely fails even after installation.

Status:

- Sample documents could not be inserted into ChromaDB.
- Embeddings could not be generated.
- Similarity search could not be executed.

## Ollama Integration

Implemented:

- `RAGEngine` calls configured Ollama URL/model.
- Prompt includes source filenames.

Failed or blocked:

- `ollama` command is not available.
- Port `11434` is not accepting connections.
- Backend config path error prevents importing `RAGEngine` cleanly in this sandbox.
- Model load could not be confirmed.
- Test prompts could not be executed.
- Response generation could not be verified.

Implementation concern:

- Code calls `POST {OLLAMA_URL}/v1/generate`, but Ollama's common native endpoint is `/api/generate`, and OpenAI-compatible endpoints are usually under `/v1/chat/completions` or `/v1/completions` depending on setup. The response parser expects `results[0].content`, which is not Ollama native response shape.

## Upload Module

Implemented:

- Upload endpoint exists at `/upload/file`.
- Supported parser methods exist for CSV, XLSX/XLS, PDF, and DOCX.
- Sample files exist:
  - `samples/training_performance.csv`
  - `samples/training_performance.xlsx`
  - `samples/war_report.pdf`
  - `samples/training_report.docx`

Failed or blocked:

- Live upload of CSV/XLSX/PDF could not be performed because backend does not start.
- Parser import failed due config trying to create `E:\SLOG PROJECTS\uploads` outside project root.
- Metadata extraction could not be verified end to end.

Implementation concerns:

- A `Document` row is committed before unsupported file-type validation; unsupported files can leave orphan document records.
- Uploaded filenames are sanitized to basename, but duplicate filenames overwrite existing files.
- No file size limit is enforced.
- No malware/content scanning or MIME validation is implemented.
- No `DocumentChunk` database records are created even though Chroma IDs are generated.

## RAG Pipeline

Implemented:

- Upload route extracts text chunks and attempts to store them in vector store.
- Chat route retrieves vector results and sends prompt to Ollama.
- Response includes `answer` and `sources`.

Failed or blocked:

- Could not upload sample documents.
- Could not ask questions through `/chat/query`.
- Could not verify source citation retrieval.

Implementation concerns:

- RAG source citations are only filenames, not chunk-level citations.
- No fallback when vector store is empty.
- No source deduplication.
- No chat history or audit detail beyond query text.

## Frontend Validation

Routes in `frontend/src/App.tsx`:

- `/` -> Login
- `/dashboard` -> Protected dashboard
- `/upload` -> Protected upload page
- `/documents` -> Protected documents page
- `/assistant` -> Protected chat page
- `*` -> Not found

Build command:

```powershell
npm.cmd run build
```

Result before install:

```text
'tsc' is not recognized as an internal or external command
```

Install command:

```powershell
npm.cmd install
```

Result:

```text
npm error notarget No matching version found for @types/react-router-dom@^6.18.2.
```

Status:

- Frontend dependencies cannot install as written.
- Frontend build could not be completed.
- TypeScript errors could not be checked.
- Login flow could not be checked in browser.
- Protected pages could not be verified live.

Code-level frontend concerns:

- `@types/react-router-dom` is unnecessary for React Router v6 and the requested version does not exist.
- `jwt-decode` v3 package export may not match `import jwtDecode from "jwt-decode"` depending on installed version.
- `isTokenExpired` is imported into `api.ts` but unused.
- Frontend stores JWT in `localStorage`, which is XSS-sensitive.
- No frontend role restrictions are wired into routes.

## Working Features

These are implemented in source code, but not all are runtime-verified:

- FastAPI app structure and router modules exist.
- JWT utility functions exist.
- RBAC helper exists.
- PostgreSQL SQLAlchemy models and schema file exist.
- Document parsers for CSV, XLSX, PDF, and DOCX exist.
- React pages for login, dashboard, upload, documents, chat, and 404 exist.
- Sample files exist.
- Docker Compose file defines PostgreSQL and backend services.
- Documentation files exist.

Runtime-verified:

- Python syntax compilation passed: `python -m compileall backend`.
- Python, Node, and `npm.cmd` are installed.
- Sample files are present.

## Failed Features

- Backend server does not start.
- Backend requirements do not install cleanly.
- Frontend dependencies do not install cleanly.
- Frontend build fails.
- PostgreSQL is not running/available in this environment.
- Ollama is not installed/running in this environment.
- ChromaDB is not installed/importable.
- Upload module cannot run because backend/config fail.
- RAG pipeline cannot run.
- Auth login/token/protected endpoint checks cannot run.
- Live RBAC validation cannot run.

## Missing Features

- Automated tests.
- Database migrations.
- Complete seed data for all documented sample users.
- Complete ORM relationships.
- Audit foreign key relationship.
- Document chunk persistence in PostgreSQL.
- Analytics dashboard backend data.
- Advanced search endpoint/UI.
- Robust source citations.
- OCR/scanned PDF support.
- File size/type validation.
- Token refresh usage in frontend.
- Production-grade secret management.

## Security Concerns

- Default JWT secret is committed and weak.
- Database password is committed in `.env` and docs.
- CORS allows all origins with credentials.
- JWT stored in `localStorage`.
- No rate limiting or login lockout.
- No file size limits, MIME validation, duplicate handling, or malware scanning.
- RBAC mismatch between documentation and implementation for Analyst uploads.
- `AuditLog.user_id` is not a foreign key.
- `Base.metadata.create_all()` on app import is risky for production.

## Performance Concerns

- Embedding model is loaded/created on each `add_documents` and query call.
- Upload endpoint processes files synchronously.
- Only first 10 chunks/rows are indexed, limiting retrieval quality.
- No background jobs for large files.
- No pagination on `/documents/list` or `/users/`.
- No vector-store/database consistency repair.
- Ollama calls use a 60-second blocking request.

## Recommended Fixes

Priority 0 - make the project runnable:

1. Pin valid backend packages:
   - `passlib[bcrypt]==1.7.4`
   - add `email-validator`
   - replace `chroma-db==0.4.0` with a valid `chromadb` version
   - verify Python 3.11/3.12 compatibility instead of Python 3.13 if ML packages fail.
2. Fix frontend package dependencies:
   - remove `@types/react-router-dom`
   - verify `jwt-decode` import for selected version.
3. Fix `UPLOAD_DIR` and `VECTOR_DIR` to point to the project root:
   - `PROJECT_ROOT = BASE_DIR.parent`
   - `UPLOAD_DIR = PROJECT_ROOT / "uploads"`
   - `VECTOR_DIR = PROJECT_ROOT / "vector_store"`
4. Install/start PostgreSQL and Ollama or provide working Docker setup.
5. Re-run backend server and frontend build.

Priority 1 - make Phase 1 functionally valid:

1. Add full seed data for documented users.
2. Add integration tests for auth, RBAC, uploads, document listing, vector search, and RAG.
3. Fix ChromaDB embedding function usage.
4. Fix Ollama endpoint and response parsing.
5. Persist document chunks in PostgreSQL.
6. Align RBAC docs and implementation.

Priority 2 - harden:

1. Move secrets to environment-only config.
2. Restrict CORS.
3. Add file validation and limits.
4. Add pagination.
5. Add database migrations.

## Completion Estimate

Phase 1 completion: 45%

Rationale: The project has meaningful scaffolding and source-level implementation, but core runtime validation fails at dependency installation, backend startup, frontend install/build, PostgreSQL, ChromaDB, Ollama, auth, upload, and RAG.

Entire project completion: 25%

Rationale: Phase 2 analytics/search/insights are mostly planned but not implemented, and Phase 1 is not yet operational.

## How To Run This Project

These are the intended run steps. Apply the recommended fixes above first, because the current dependency files do not install successfully as written.

### Backend

```powershell
cd "E:\SLOG PROJECTS\AI INTELLIGENCE"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
```

Create/start PostgreSQL with:

- database: `atip`
- user: `atip_user`
- password: `atip_pass`
- URL: `postgresql+psycopg2://atip_user:atip_pass@localhost:5432/atip`

Then seed and run:

```powershell
$env:PYTHONPATH = "E:\SLOG PROJECTS\AI INTELLIGENCE\backend"
python scripts\seed_db.py
python -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

Open backend docs:

```text
http://127.0.0.1:8000/docs
```

### Ollama

Install Ollama, then:

```powershell
ollama pull qwen3
ollama serve
```

Verify:

```powershell
curl http://localhost:11434/api/tags
```

### Frontend

```powershell
cd "E:\SLOG PROJECTS\AI INTELLIGENCE\frontend"
npm.cmd install
npm.cmd run dev
```

Open:

```text
http://localhost:5173
```

Default documented login after seed:

```text
admin / Admin123!
```

