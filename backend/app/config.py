"""
ATIP Configuration
==================
Central configuration for the entire backend.
Override any value via environment variables or backend/.env file.

Supported LLMs (set OLLAMA_MODEL):
  - qwen3:8b            (default, fast)
  - qwen3:14b
  - qwen3:32b
  - deepseek-r1:14b
  - deepseek-r1:32b
  - llama3.3:70b
  - llama3.1:8b

Supported Embedding Models (set EMBEDDING_MODEL):
  - BAAI/bge-large-en-v1.5   (default, 1024-dim, best quality)
  - BAAI/bge-m3              (multilingual, best for mixed-language docs)
  - all-MiniLM-L6-v2         (fallback, fast, 384-dim)
"""

import os
from pathlib import Path
from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent
load_dotenv(BACKEND_DIR / ".env")

# ── Database ──────────────────────────────────────────────────────────────────
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://atip_user:atip_pass@localhost:5432/atip",
)

# ── Auth ──────────────────────────────────────────────────────────────────────
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-me-secret")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

# ── LLM (Ollama) ─────────────────────────────────────────────────────────────
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:8b")

# ── Embedding Model ───────────────────────────────────────────────────────────
# BAAI/bge-large-en-v1.5 → high-quality 1024-dim English embeddings (recommended)
# BAAI/bge-m3            → multilingual, slightly slower
# all-MiniLM-L6-v2       → fast fallback if BGE not downloaded
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-large-en-v1.5")

# ── RAG Pipeline ─────────────────────────────────────────────────────────────
# Number of candidate chunks to retrieve before reranking
RAG_RETRIEVE_TOP_K = int(os.getenv("RAG_RETRIEVE_TOP_K", "50"))
# Number of chunks sent to LLM after reranking (8–12 recommended)
RAG_RERANK_TOP_K = int(os.getenv("RAG_RERANK_TOP_K", "10"))
# Approximate token budget for context window (adjust per model)
RAG_MAX_CONTEXT_TOKENS = int(os.getenv("RAG_MAX_CONTEXT_TOKENS", "6000"))

# ── File Storage ──────────────────────────────────────────────────────────────
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", PROJECT_ROOT / "uploads")).resolve()
VECTOR_DIR = Path(os.getenv("VECTOR_DIR", PROJECT_ROOT / "vector_store")).resolve()

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
VECTOR_DIR.mkdir(parents=True, exist_ok=True)

# ── Document Processing ───────────────────────────────────────────────────────
# Chunk size in characters (800 ≈ 200 tokens; good for BGE retrieval)
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "800"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "150"))
# Maximum simultaneous documents to index (production limit)
MAX_SIMULTANEOUS_DOCS = int(os.getenv("MAX_SIMULTANEOUS_DOCS", "5"))