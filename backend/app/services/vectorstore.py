"""
ATIP Enterprise VectorStore
==============================
Production-grade hybrid retrieval:
  - Semantic Vector Search  (BAAI/bge-large-en-v1.5 or bge-m3)
  - BM25 Keyword Search      (rank_bm25)
  - Entity / Metadata Search (alias-aware)
  - Candidate pool: ~50 chunks across ALL indexed documents
  - FlashRank reranker → best 8–12 chunks sent to LLM
  - Deduplication + diversity preservation

ROOT CAUSE FIX (meta tensor / SentenceTransformer crash):
  torch 2.x CUDA builds shipped without a real GPU will place model weights on
  the synthetic 'meta' device during initialisation.  Calling .to(device) on a
  meta tensor raises:
      "Cannot copy out of meta tensor; no data!  Please use
       torch.nn.Module.to_empty() instead of torch.nn.Module.to()"
  The fix is threefold:
    1.  Detect the safe device BEFORE loading any model (cuda only if
        torch.cuda.is_available() is True, otherwise cpu).
    2.  Pass device= explicitly to SentenceTransformer so it never tries to
        auto-detect and land on a CUDA device that has no backing memory.
    3.  Load the SentenceTransformer model ONCE as a module-level singleton so
        that every VectorStore instance — created during upload, delete, query
        or stats — reuses the already-loaded weights in RAM.  This prevents
        repeated model loads that each risk triggering the meta-tensor path and
        that waste several seconds per request.

ChromaDB >=1.0.0 compatibility:
  BGEEmbeddingFunction subclasses EmbeddingFunction[Documents] and implements
  all required protocol methods: __call__, name(), get_config(),
  build_from_config().
"""

import json
import logging
import re
import threading
from typing import Any, Dict, List, Optional, Tuple

import chromadb
import numpy as np
from chromadb import EmbeddingFunction, Documents, Embeddings
from rank_bm25 import BM25Okapi

from ..config import VECTOR_DIR, EMBEDDING_MODEL

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# Device selection — done ONCE at import time
# ─────────────────────────────────────────────
def _safe_device() -> str:
    """
    Return 'cuda' only when a real GPU is present and CUDA-capable torch is
    installed.  Never return 'cuda' on a CUDA-build with zero visible GPUs —
    that is exactly what triggers the meta-tensor error.
    """
    try:
        import torch
        if torch.cuda.is_available() and torch.cuda.device_count() > 0:
            logger.info("GPU detected — using CUDA for embeddings")
            return "cuda"
    except Exception as exc:
        logger.warning(f"torch device check failed ({exc}); defaulting to cpu")
    logger.info("No GPU available — using CPU for embeddings")
    return "cpu"


_EMBED_DEVICE: str = _safe_device()


# ─────────────────────────────────────────────
# Military Alias Resolver
# ─────────────────────────────────────────────
_RANK_ABBR = {
    "gen": "general",
    "lt gen": "lieutenant general",
    "maj gen": "major general",
    "brig": "brigadier",
    "col": "colonel",
    "lt col": "lieutenant colonel",
    "maj": "major",
    "capt": "captain",
    "lt": "lieutenant",
    "2lt": "second lieutenant",
    "sub": "subedar",
    "hav": "havildar",
    "nk": "naik",
    "sep": "sepoy",
    "rfn": "rifleman",
    "spr": "sapper",
    "gnr": "gunner",
}


def _normalise_query(query: str) -> str:
    """Expand rank abbreviations so semantic search can match full forms."""
    q = query
    for abbr, full in _RANK_ABBR.items():
        q = re.sub(rf'\b{re.escape(abbr)}\b', full, q, flags=re.IGNORECASE)
    return q


def _build_alias_variants(query: str) -> List[str]:
    """
    Generate plausible name variants from a query so we can search
    for all of them in metadata.
    E.g. "Capt Jatin Verma" → ["Jatin Verma", "Verma", "Captain Jatin Verma", ...]
    """
    variants = [query]
    stripped = re.sub(
        r'\b(?:Captain|Capt|Major|Maj|Colonel|Col|General|Gen|Lieutenant|Lt|'
        r'Brigadier|Brig|Subedar|Sub|Havildar|Hav|Sepoy|Sep)\s+',
        '', query, flags=re.IGNORECASE
    ).strip()
    if stripped and stripped != query:
        variants.append(stripped)
        parts = stripped.split()
        if len(parts) >= 2:
            variants.append(parts[-1])
            variants.append(" ".join(parts[:2]))

    return list(dict.fromkeys(variants))


# ─────────────────────────────────────────────
# Module-level SentenceTransformer singleton
# ─────────────────────────────────────────────
# The model is loaded exactly once per process, thread-safely, and reused by
# every BGEEmbeddingFunction / VectorStore instance created afterwards.
# This eliminates:
#   - Per-request model reloads (slow, risky)
#   - Meta-tensor errors from repeated device moves
#   - Memory leaks from duplicate model weights in RAM

_ST_MODEL = None          # SentenceTransformer instance
_ST_MODEL_NAME: str = ""  # which model was actually loaded
_ST_IS_BGE: bool = False  # whether BGE instruction prefixes should be used
_ST_LOCK = threading.Lock()


def _load_sentence_transformer(model_name: str):
    """
    Load SentenceTransformer once, thread-safely, with an explicit CPU/CUDA
    device so torch never attempts a meta-device initialisation.

    Falls back to all-MiniLM-L6-v2 if the requested model is unavailable,
    e.g. because the BGE weights have not been downloaded yet.
    """
    global _ST_MODEL, _ST_MODEL_NAME, _ST_IS_BGE

    with _ST_LOCK:
        if _ST_MODEL is not None:
            # Already loaded by a previous request; nothing to do.
            logger.debug(f"Reusing cached SentenceTransformer '{_ST_MODEL_NAME}'")
            return

        from sentence_transformers import SentenceTransformer

        # ── Attempt 1: requested model ──────────────────────────────────────
        try:
            logger.info(
                f"Loading SentenceTransformer '{model_name}' on device='{_EMBED_DEVICE}'"
            )
            model = SentenceTransformer(model_name, device=_EMBED_DEVICE)
            _ST_MODEL = model
            _ST_MODEL_NAME = model_name
            _ST_IS_BGE = "bge" in model_name.lower()
            logger.info(
                f"SentenceTransformer '{model_name}' ready "
                f"(dims={model.get_sentence_embedding_dimension()}, "
                f"device={_EMBED_DEVICE})"
            )
            return
        except Exception as primary_exc:
            logger.warning(
                f"Could not load '{model_name}' on device='{_EMBED_DEVICE}': "
                f"{primary_exc}"
            )

        # ── Attempt 2: force CPU in case device choice caused the failure ───
        if _EMBED_DEVICE != "cpu":
            try:
                logger.info(f"Retrying '{model_name}' on device='cpu'")
                model = SentenceTransformer(model_name, device="cpu")
                _ST_MODEL = model
                _ST_MODEL_NAME = model_name
                _ST_IS_BGE = "bge" in model_name.lower()
                logger.info(f"SentenceTransformer '{model_name}' loaded on cpu (fallback)")
                return
            except Exception as cpu_exc:
                logger.warning(f"CPU retry for '{model_name}' also failed: {cpu_exc}")

        # ── Attempt 3: fallback model on CPU ────────────────────────────────
        fallback = "all-MiniLM-L6-v2"
        try:
            logger.warning(
                f"Falling back to '{fallback}' after failing to load '{model_name}'"
            )
            model = SentenceTransformer(fallback, device="cpu")
            _ST_MODEL = model
            _ST_MODEL_NAME = fallback
            _ST_IS_BGE = False
            logger.info(f"SentenceTransformer fallback '{fallback}' loaded on cpu")
        except Exception as fallback_exc:
            # Nothing works — log a clear, actionable error.
            logger.error(
                f"FATAL: Could not load any SentenceTransformer model. "
                f"Primary='{model_name}', fallback='{fallback}'. "
                f"Last error: {fallback_exc}. "
                f"Ensure sentence-transformers is installed and model weights "
                f"are present in the HuggingFace cache.",
                exc_info=True,
            )
            raise RuntimeError(
                f"SentenceTransformer initialisation failed for both "
                f"'{model_name}' and '{fallback}': {fallback_exc}"
            ) from fallback_exc


def _get_st_model():
    """Return the cached SentenceTransformer, loading it on first call."""
    if _ST_MODEL is None:
        _load_sentence_transformer(EMBEDDING_MODEL)
    return _ST_MODEL


# ─────────────────────────────────────────────
# BGE Embedding Function (ChromaDB >=1.0.0)
# ─────────────────────────────────────────────
class BGEEmbeddingFunction(EmbeddingFunction[Documents]):
    """
    ChromaDB >=1.0.0 EmbeddingFunction backed by the module-level
    SentenceTransformer singleton.

    ChromaDB 1.x required protocol:
      __call__           — embed a list of documents (used for upsert)
      name()             — unique static string identifier
      get_config()       — serialisable config dict
      build_from_config  — reconstruct from config dict

    BGE instruction prefixes are applied automatically:
      Documents  → "Represent this military document for retrieval: <text>"
      Queries    → "Represent this query for searching military intelligence
                    documents: <text>"
    These prefixes are the official BGE recommendation and significantly
    improve retrieval quality; they are omitted for non-BGE fallbacks.
    """

    _DOC_PREFIX   = "Represent this military document for retrieval: "
    _QUERY_PREFIX = "Represent this query for searching military intelligence documents: "

    def __init__(self, model_name: str = "BAAI/bge-large-en-v1.5"):
        # Trigger singleton load (no-op if already loaded).
        _load_sentence_transformer(model_name)
        # Hold a reference; do NOT store a copy of model weights.
        self._model_name = _ST_MODEL_NAME   # may differ from model_name if fallback used
        self.dimensions  = _ST_MODEL.get_sentence_embedding_dimension()

    # ── ChromaDB 1.x protocol ────────────────────────────────────────────────

    def __call__(self, input: Documents) -> Embeddings:
        """Called by ChromaDB during collection.upsert() and collection.query()."""
        return self._embed_passages(list(input))

    @staticmethod
    def name() -> str:
        """Unique identifier required by ChromaDB >=1.0."""
        return "bge_embedding_function"

    def get_config(self) -> Dict[str, Any]:
        """Serialisable config for ChromaDB persistence."""
        return {"model_name": self._model_name}

    @staticmethod
    def build_from_config(config: Dict[str, Any]) -> "BGEEmbeddingFunction":
        """Reconstruct from persisted config (required by ChromaDB >=1.0)."""
        return BGEEmbeddingFunction(
            model_name=config.get("model_name", "BAAI/bge-large-en-v1.5")
        )

    # ── Embedding helpers (used internally and by RAGEngine) ────────────────

    def _embed_passages(self, texts: List[str]) -> List[List[float]]:
        """Embed document passages with the BGE retrieval instruction prefix."""
        if not texts:
            return []
        model = _get_st_model()
        if _ST_IS_BGE:
            texts = [f"{self._DOC_PREFIX}{t}" for t in texts]
        try:
            embeddings = model.encode(
                texts,
                batch_size=32,
                show_progress_bar=False,
                normalize_embeddings=True,
            )
            return embeddings.tolist()
        except Exception as exc:
            logger.error(
                f"Document embedding failed (model='{_ST_MODEL_NAME}', "
                f"batch_size={len(texts)}): {exc}",
                exc_info=True,
            )
            raise

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Public alias used by RAGEngine directly."""
        return self._embed_passages(texts)

    def embed_query(self, query: str) -> List[float]:
        """
        Embed a single query string with the BGE query instruction prefix.
        Uses a separate prefix from document passages per BGE specification.
        Called directly by RAGEngine for similarity computation.
        """
        model = _get_st_model()
        prefixed = f"{self._QUERY_PREFIX}{query}" if _ST_IS_BGE else query
        try:
            embedding = model.encode(
                [prefixed],
                normalize_embeddings=True,
            )
            return embedding[0].tolist()
        except Exception as exc:
            logger.error(
                f"Query embedding failed (model='{_ST_MODEL_NAME}'): {exc}",
                exc_info=True,
            )
            raise


# ─────────────────────────────────────────────
# Module-level ChromaDB client singleton
# ─────────────────────────────────────────────
# One PersistentClient per process prevents "database is locked" errors when
# multiple background tasks attempt concurrent writes, and avoids re-opening
# the SQLite WAL file on every VectorStore() construction.

_CHROMA_CLIENT: Optional[chromadb.PersistentClient] = None
_CHROMA_LOCK = threading.Lock()


def _get_chroma_client() -> chromadb.PersistentClient:
    global _CHROMA_CLIENT
    if _CHROMA_CLIENT is None:
        with _CHROMA_LOCK:
            if _CHROMA_CLIENT is None:
                try:
                    _CHROMA_CLIENT = chromadb.PersistentClient(path=str(VECTOR_DIR))
                    logger.info(f"ChromaDB PersistentClient opened at '{VECTOR_DIR}'")
                except Exception as exc:
                    logger.error(
                        f"Failed to open ChromaDB at '{VECTOR_DIR}': {exc}",
                        exc_info=True,
                    )
                    raise
    return _CHROMA_CLIENT


# ─────────────────────────────────────────────
# BM25 Index (in-memory, rebuilt on demand)
# ─────────────────────────────────────────────
class BM25Index:
    """Lightweight BM25 index wrapping all documents in a ChromaDB collection."""

    def __init__(self):
        self._corpus_ids:   List[str] = []
        self._corpus_texts: List[str] = []
        self._bm25: Optional[BM25Okapi] = None

    def build(self, ids: List[str], texts: List[str]):
        self._corpus_ids   = ids
        self._corpus_texts = texts
        tokenised = [t.lower().split() for t in texts]
        self._bm25 = BM25Okapi(tokenised)
        logger.debug(f"BM25 index built with {len(ids)} documents")

    def search(self, query: str, n_results: int = 30) -> List[Tuple[str, float]]:
        if self._bm25 is None or not self._corpus_ids:
            return []
        tokens = query.lower().split()
        scores = self._bm25.get_scores(tokens)
        ranked = sorted(
            zip(self._corpus_ids, scores),
            key=lambda x: x[1],
            reverse=True,
        )
        return [
            (doc_id, float(score))
            for doc_id, score in ranked[:n_results]
            if score > 0
        ]


# ─────────────────────────────────────────────
# Enterprise VectorStore
# ─────────────────────────────────────────────
class VectorStore:
    """
    Thin façade over ChromaDB + BM25.

    Construction is intentionally cheap: it reuses the module-level
    BGEEmbeddingFunction (which reuses the module-level SentenceTransformer)
    and the module-level ChromaDB PersistentClient.  No model weights are
    loaded on construction after the first call.

    Safe to call from:
      - upload background tasks (multiple concurrent documents)
      - delete endpoint
      - chat query endpoint
      - stats endpoint
    without re-initialising or reloading anything.
    """

    def __init__(self, collection_name: str = "atip_documents"):
        # Reuse the singleton embedding function (loads model on first call).
        self.embedding_fn = BGEEmbeddingFunction(EMBEDDING_MODEL)
        # Reuse the singleton ChromaDB client.
        self.client = _get_chroma_client()

        try:
            self.collection = self.client.get_or_create_collection(
                name=collection_name,
                embedding_function=self.embedding_fn,
                metadata={"hnsw:space": "cosine"},
            )
            logger.debug(
                f"Collection '{collection_name}' ready "
                f"({self.collection.count()} chunks)"
            )
        except Exception as exc:
            logger.error(
                f"Failed to get/create ChromaDB collection '{collection_name}': {exc}",
                exc_info=True,
            )
            raise

        self._bm25 = BM25Index()
        self._bm25_dirty = True

    # ── CRUD ─────────────────────────────────────────────────────────────────

    def add_documents(
        self,
        texts:     List[str],
        metadatas: List[dict],
        ids:       List[str],
    ):
        if not texts:
            logger.warning("add_documents called with empty list — skipping")
            return
        flat_metas = [_flatten_metadata(m) for m in metadatas]
        try:
            self.collection.upsert(
                documents=texts,
                metadatas=flat_metas,
                ids=ids,
            )
            self._bm25_dirty = True
            logger.debug(f"Upserted {len(texts)} chunks into '{self.collection.name}'")
        except Exception as exc:
            logger.error(
                f"ChromaDB upsert failed ({len(texts)} chunks): {exc}",
                exc_info=True,
            )
            raise

    def delete_by_ids(self, ids: List[str]):
        if not ids:
            return
        try:
            self.collection.delete(ids=ids)
            self._bm25_dirty = True
            logger.debug(f"Deleted {len(ids)} vectors from '{self.collection.name}'")
        except Exception as exc:
            logger.error(
                f"ChromaDB delete failed ({len(ids)} ids): {exc}",
                exc_info=True,
            )
            raise

    def count(self) -> int:
        try:
            return self.collection.count()
        except Exception as exc:
            logger.error(f"ChromaDB count failed: {exc}", exc_info=True)
            return 0

    # ── BM25 rebuild ─────────────────────────────────────────────────────────

    def _ensure_bm25(self):
        if not self._bm25_dirty:
            return
        total = self.collection.count()
        if total == 0:
            self._bm25_dirty = False
            return
        batch_size = 5000
        all_ids:   List[str] = []
        all_texts: List[str] = []
        offset = 0
        while offset < total:
            result = self.collection.get(
                limit=batch_size,
                offset=offset,
                include=["documents"],
            )
            all_ids.extend(result["ids"])
            all_texts.extend(result["documents"])
            offset += batch_size
        self._bm25.build(all_ids, all_texts)
        self._bm25_dirty = False

    # ── Hybrid retrieval ──────────────────────────────────────────────────────

    def query(
        self,
        query_text:   str,
        n_results:    int = 50,
        document_ids: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        """
        Hybrid retrieval:
          1. Semantic vector search (BGE embeddings)
          2. BM25 keyword search
          3. Entity / alias metadata search
        Returns up to n_results unique candidate chunks.
        """
        _EMPTY = {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}

        total = self.count()
        if total == 0:
            logger.warning("query() on empty collection")
            return _EMPTY

        n_fetch = min(n_results, total)
        normalised = _normalise_query(query_text)
        aliases    = _build_alias_variants(query_text)

        # ── 1. Semantic search ────────────────────────────────────────────────
        where_filter = None
        if document_ids:
            where_filter = {
                "document_id": {"$in": [str(d) for d in document_ids]}
            }

        try:
            sem = self.collection.query(
                query_texts=[normalised],
                n_results=n_fetch,
                where=where_filter,
                include=["documents", "metadatas", "distances"],
            )
        except Exception as exc:
            logger.error(f"Semantic search failed: {exc}", exc_info=True)
            return _EMPTY

        candidates: Dict[str, Dict[str, Any]] = {}
        for idx, cid in enumerate(sem["ids"][0]):
            # cosine distance ∈ [0,2] → similarity ∈ [0,1]
            score = 1.0 - (sem["distances"][0][idx] / 2.0)
            candidates[cid] = {
                "id":       cid,
                "document": sem["documents"][0][idx],
                "metadata": sem["metadatas"][0][idx],
                "score":    score,
                "sources":  ["semantic"],
            }

        # ── 2. BM25 search ────────────────────────────────────────────────────
        self._ensure_bm25()
        bm25_hits = self._bm25.search(normalised, n_results=n_fetch)
        if bm25_hits:
            max_bm25 = max(s for _, s in bm25_hits) or 1.0
            for doc_id, raw in bm25_hits:
                norm_score = raw / max_bm25
                if doc_id in candidates:
                    candidates[doc_id]["score"] = (
                        candidates[doc_id]["score"] * 0.6 + norm_score * 0.4
                    )
                    candidates[doc_id]["sources"].append("bm25")
                else:
                    try:
                        fetched = self.collection.get(
                            ids=[doc_id],
                            include=["documents", "metadatas"],
                        )
                        if fetched["ids"]:
                            candidates[doc_id] = {
                                "id":       doc_id,
                                "document": fetched["documents"][0],
                                "metadata": fetched["metadatas"][0],
                                "score":    norm_score * 0.4,
                                "sources":  ["bm25"],
                            }
                    except Exception:
                        pass

        # ── 3. Entity / alias search ──────────────────────────────────────────
        for variant in aliases:
            if not variant.strip():
                continue
            try:
                ent = self.collection.query(
                    query_texts=[variant],
                    n_results=min(10, total),
                    include=["documents", "metadatas", "distances"],
                )
                for idx, cid in enumerate(ent["ids"][0]):
                    ent_score = 1.0 - (ent["distances"][0][idx] / 2.0)
                    if cid in candidates:
                        candidates[cid]["score"] = max(
                            candidates[cid]["score"], ent_score * 0.5
                        )
                        if "entity" not in candidates[cid]["sources"]:
                            candidates[cid]["sources"].append("entity")
                    else:
                        candidates[cid] = {
                            "id":       cid,
                            "document": ent["documents"][0][idx],
                            "metadata": ent["metadatas"][0][idx],
                            "score":    ent_score * 0.5,
                            "sources":  ["entity"],
                        }
            except Exception:
                pass

        # ── Deduplicate, sort, trim ───────────────────────────────────────────
        unique = _deduplicate_candidates(list(candidates.values()))
        unique.sort(key=lambda x: x["score"], reverse=True)
        unique = unique[:n_results]

        return {
            "ids":       [[c["id"]       for c in unique]],
            "documents": [[c["document"] for c in unique]],
            "metadatas": [[c["metadata"] for c in unique]],
            "distances": [[1.0 - c["score"] for c in unique]],
        }


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def _flatten_metadata(meta: Dict[str, Any]) -> Dict[str, Any]:
    """
    ChromaDB only stores str / int / float / bool metadata values.
    Serialise dicts and lists to JSON strings.
    """
    flat: Dict[str, Any] = {}
    for k, v in meta.items():
        if k == "entities" and isinstance(v, dict):
            flat["entities_json"] = json.dumps(v)
            for ek, ev in v.items():
                if isinstance(ev, list):
                    flat[f"entities_{ek}"] = json.dumps(ev)
        elif isinstance(v, (dict, list)):
            flat[k] = json.dumps(v)
        elif isinstance(v, bool):
            flat[k] = int(v)
        elif v is None:
            flat[k] = ""
        else:
            flat[k] = v
    return flat


def _deduplicate_candidates(
    candidates: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Remove near-duplicate chunks via text fingerprinting."""
    seen: set = set()
    deduped: List[Dict[str, Any]] = []
    for c in candidates:
        fp = re.sub(r'\s+', ' ', c.get("document", "")[:120].lower()).strip()
        if fp in seen:
            continue
        seen.add(fp)
        deduped.append(c)
    return deduped