"""
ATIP Enterprise RAG Engine
============================
Production-grade query pipeline:
  1. Hybrid retrieval  → ~50 candidates from ALL documents
  2. FlashRank rerank  → top 8–12 chunks
  3. Context compression (dedup + diversity)
  4. Anti-hallucination prompt with evidence anchoring
  5. Cross-document reasoning (compare, summarise, multi-source)
  6. Structured citation output (filename, page, section)
  7. Conversation memory
  8. Configurable Ollama backend (Qwen3 14B/32B, DeepSeek R1, Llama 3.3 70B, …)
  9. Retry logic with exponential back-off
  10. Streaming support via generator
"""

import json
import logging
import re
import time
from typing import Any, Dict, Generator, List, Optional

import requests
from flashrank import Ranker, RerankRequest

from ..config import OLLAMA_URL, OLLAMA_MODEL

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# Reranker – FlashRank ms-marco reranker
# ─────────────────────────────────────────────
_RANKER_CACHE: Optional[Ranker] = None


def _get_ranker() -> Ranker:
    global _RANKER_CACHE
    if _RANKER_CACHE is None:
        try:
            _RANKER_CACHE = Ranker(
                model_name="ms-marco-MultiBERT-L-12",
                cache_dir="/tmp/flashrank_cache",
            )
        except Exception:
            # Fallback to lighter model
            _RANKER_CACHE = Ranker(
                model_name="ms-marco-MiniLM-L-12-v2",
                cache_dir="/tmp/flashrank_cache",
            )
    return _RANKER_CACHE


# ─────────────────────────────────────────────
# Context Compression Helpers
# ─────────────────────────────────────────────
def _compress_context(chunks: List[Dict[str, Any]], max_tokens: int = 6000) -> List[Dict[str, Any]]:
    """
    Keep chunks until estimated token budget is exhausted.
    Prefer diversity: if many chunks are from the same document+page, thin them.
    """
    selected: List[Dict[str, Any]] = []
    seen_page_keys: Dict[str, int] = {}   # key=doc+page → count
    total_chars = 0
    # rough char→token ratio ≈ 4
    char_limit = max_tokens * 4

    for chunk in chunks:
        text_len = len(chunk.get("document", ""))
        meta = chunk.get("metadata", {})
        filename = meta.get("original_filename") or meta.get("filename", "unknown")
        page = meta.get("page_number", "")
        key = f"{filename}::{page}"
        already = seen_page_keys.get(key, 0)
        # Allow at most 2 chunks per (doc, page) to preserve cross-doc diversity
        if already >= 2:
            continue
        if total_chars + text_len > char_limit and selected:
            break
        selected.append(chunk)
        seen_page_keys[key] = already + 1
        total_chars += text_len

    return selected


# ─────────────────────────────────────────────
# Prompt Builder
# ─────────────────────────────────────────────
def _build_rag_prompt(
    query: str,
    sources: List[Dict[str, Any]],
    history: str = "",
    is_cross_doc: bool = False,
) -> str:
    """
    Build a structured, anti-hallucination RAG prompt.
    Every context block carries [SOURCE N] tag for citation.
    """
    context_blocks: List[str] = []
    for i, src in enumerate(sources):
        meta = src.get("metadata", {})
        filename = meta.get("original_filename") or meta.get("filename", "unknown")
        page_num = meta.get("page_number")
        section = meta.get("section", "")

        label = f"SOURCE {i + 1}: {filename}"
        if page_num:
            label += f" (Page {page_num})"
        if section and section not in ("Document Start", filename):
            label += f" — Section: {section}"

        context_blocks.append(f"[{label}]\n{src['document']}")

    context = "\n\n".join(context_blocks)

    cross_doc_instruction = ""
    if is_cross_doc:
        cross_doc_instruction = (
            "\n8. This query requires reasoning across MULTIPLE documents. "
            "Compare, contrast, and synthesise evidence from all relevant sources. "
            "Clearly attribute each piece of evidence to its source using [SOURCE N] citations."
        )

    history_block = f"\nCONVERSATION HISTORY:\n{history}\n" if history else ""

    return (
        "You are the Army Training Intelligence Platform (ATIP) Assistant — "
        "a highly specialised military intelligence AI operating in a fully offline environment.\n\n"
        "STRICT RULES:\n"
        "1. Answer ONLY from the CONTEXT provided below. Do NOT use any outside knowledge.\n"
        "2. If the answer is NOT in the context, respond EXACTLY: "
        "\"The uploaded documents do not contain information about [topic]. "
        "Please upload the relevant document or rephrase your query.\"\n"
        "3. Never guess, infer beyond evidence, or fill gaps with plausible-sounding information.\n"
        "4. Cite every factual claim using [SOURCE N: filename (Page X)] notation.\n"
        "5. Use professional military terminology.\n"
        "6. For numerical data, extract exact figures from context — never round or estimate.\n"
        "7. End your answer with a confidence assessment: "
        "CONFIDENCE: HIGH | MEDIUM | LOW, and a brief reason."
        f"{cross_doc_instruction}\n"
        f"{history_block}\n"
        "CONTEXT (from indexed military documents):\n"
        "─────────────────────────────────────────\n"
        f"{context}\n"
        "─────────────────────────────────────────\n\n"
        f"QUERY: {query}\n\n"
        "INTELLIGENCE ASSESSMENT:"
    )


def _build_summary_prompt(filename: str, content: str) -> str:
    return (
        f"You are a military intelligence analyst. "
        f"Analyse the document '{filename}' and produce a structured summary.\n\n"
        f"DOCUMENT CONTENT (first 4000 chars):\n{content[:4000]}\n\n"
        "Respond with the following structure:\n"
        "**Document Overview**: (1–2 sentences)\n"
        "**Key Intelligence Findings**: (3–5 bullet points)\n"
        "**Personnel Mentioned**: (officers, ranks, names)\n"
        "**Units/Formations**: (battalion, regiment, company)\n"
        "**Operations/Exercises**: (if any)\n"
        "**Weapons/Equipment**: (if any)\n"
        "**Critical Figures/Statistics**: (exact numbers from the text)\n"
        "**Recommendations**: (actionable military intelligence)"
    )


# ─────────────────────────────────────────────
# Cross-Document Detection
# ─────────────────────────────────────────────
_CROSS_DOC_KEYWORDS = re.compile(
    r'\b(compare|comparison|across|between|all\s+documents?|both\s+documents?|'
    r'multiple|summarize\s+all|overall|combined|aggregate|versus|vs\.?)\b',
    re.IGNORECASE,
)


def _is_cross_doc_query(query: str) -> bool:
    return bool(_CROSS_DOC_KEYWORDS.search(query))


# ─────────────────────────────────────────────
# Main RAG Engine
# ─────────────────────────────────────────────
class RAGEngine:
    def __init__(
        self,
        vector_store,
        top_k_retrieve: int = 50,
        top_k_rerank: int = 10,
        max_context_tokens: int = 6000,
    ):
        self.vector_store = vector_store
        self.top_k_retrieve = top_k_retrieve
        self.top_k_rerank = top_k_rerank
        self.max_context_tokens = max_context_tokens

    # ── Public Query Interface ────────────────
    def query(
        self,
        query: str,
        history: str = "",
        document_ids: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        """
        Full RAG pipeline:
          retrieve → rerank → compress → prompt → LLM → parse citations
        """
        try:
            # 1. Hybrid retrieval
            raw_results = self.vector_store.query(
                query_text=query,
                n_results=self.top_k_retrieve,
                document_ids=document_ids,
            )

            if not raw_results or not raw_results.get("ids") or not raw_results["ids"][0]:
                return {
                    "answer": (
                        "The uploaded documents do not contain any indexed content yet. "
                        "Please upload and wait for processing to complete."
                    ),
                    "sources": [],
                    "confidence": None,
                }

            # 2. Flatten results to passage list
            passages: List[Dict[str, Any]] = []
            for idx in range(len(raw_results["ids"][0])):
                passages.append({
                    "text": raw_results["documents"][0][idx],
                    "meta": raw_results["metadatas"][0][idx],
                    "score": 1.0 - (raw_results["distances"][0][idx]),
                })

            # 3. FlashRank reranking
            reranked = self._rerank(query, passages)

            # 4. Context compression + diversity preservation
            final_chunks = _compress_context(reranked, max_tokens=self.max_context_tokens)

            if not final_chunks:
                return {
                    "answer": (
                        "The uploaded documents do not contain information relevant to your query. "
                        "Please rephrase or upload additional documents."
                    ),
                    "sources": [],
                    "confidence": None,
                }

            # 5. Build structured sources list
            structured_sources = self._build_source_list(final_chunks)
            is_cross = _is_cross_doc_query(query)

            # 6. LLM call with retry
            prompt = _build_rag_prompt(query, final_chunks, history=history, is_cross_doc=is_cross)
            raw_answer = self._call_ollama_with_retry(prompt)

            # 7. Post-process: strip <think> blocks, extract confidence
            answer, thought, confidence = self._post_process(raw_answer)

            return {
                "answer": answer,
                "thought": thought,
                "sources": structured_sources,
                "confidence": confidence,
            }

        except Exception as e:
            logger.error(f"RAG query error: {e}", exc_info=True)
            return {
                "answer": f"Intelligence Engine Error: {str(e)}",
                "sources": [],
                "confidence": None,
            }

    def summarize_document(self, filename: str, content: str) -> str:
        try:
            prompt = _build_summary_prompt(filename, content)
            raw = self._call_ollama_with_retry(prompt, max_tokens=1024)
            answer, _, _ = self._post_process(raw)
            return answer
        except Exception as e:
            logger.error(f"Summarization error: {e}")
            return "Failed to generate document summary."

    def stream_query(
        self,
        query: str,
        history: str = "",
        document_ids: Optional[List[int]] = None,
    ) -> Generator[str, None, None]:
        """
        Streaming RAG pipeline — yields JSON-encoded delta tokens.
        Each yielded string is: data: <json>\n\n  (Server-Sent Events format)
        Final event: data: [DONE]\n\n
        """
        try:
            raw_results = self.vector_store.query(
                query_text=query,
                n_results=self.top_k_retrieve,
                document_ids=document_ids,
            )

            if not raw_results or not raw_results.get("ids") or not raw_results["ids"][0]:
                yield f"data: {json.dumps({'type': 'answer', 'token': 'The uploaded documents do not contain any indexed content yet.'})}\n\n"
                yield "data: [DONE]\n\n"
                return

            passages = [
                {
                    "text": raw_results["documents"][0][idx],
                    "meta": raw_results["metadatas"][0][idx],
                    "score": 1.0 - raw_results["distances"][0][idx],
                }
                for idx in range(len(raw_results["ids"][0]))
            ]

            reranked = self._rerank(query, passages)
            final_chunks = _compress_context(reranked, max_tokens=self.max_context_tokens)

            if not final_chunks:
                yield f"data: {json.dumps({'type': 'answer', 'token': 'No relevant context found.'})}\n\n"
                yield "data: [DONE]\n\n"
                return

            structured_sources = self._build_source_list(final_chunks)
            is_cross = _is_cross_doc_query(query)
            prompt = _build_rag_prompt(query, final_chunks, history=history, is_cross_doc=is_cross)

            # Emit sources metadata first
            yield f"data: {json.dumps({'type': 'sources', 'sources': structured_sources})}\n\n"

            # Stream tokens from Ollama
            for token in self._stream_ollama(prompt):
                yield f"data: {json.dumps({'type': 'token', 'token': token})}\n\n"

            yield "data: [DONE]\n\n"

        except Exception as e:
            logger.error(f"Streaming RAG error: {e}", exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
            yield "data: [DONE]\n\n"

    # ── Reranking ────────────────────────────
    def _rerank(
        self,
        query: str,
        passages: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Rerank using FlashRank.  Falls back to vector-score ordering on failure.
        Returns list of dicts with 'document', 'metadata', 'score' keys.
        """
        if not passages:
            return []

        try:
            ranker = _get_ranker()
            rr_passages = [{"text": p["text"], "meta": p["meta"]} for p in passages]
            rr_req = RerankRequest(query=query, passages=rr_passages)
            reranked = ranker.rerank(rr_req)

            result: List[Dict[str, Any]] = []
            for item in reranked[: self.top_k_rerank]:
                result.append({
                    "document": item["text"],
                    "metadata": item["meta"],
                    "score": float(item.get("score", 0.5)),
                })
            return result

        except Exception as e:
            logger.warning(f"Reranker failed ({e}), falling back to retrieval order.")
            sorted_p = sorted(passages, key=lambda x: x["score"], reverse=True)
            return [
                {"document": p["text"], "metadata": p["meta"], "score": p["score"]}
                for p in sorted_p[: self.top_k_rerank]
            ]

    # ── Source List Builder ───────────────────
    @staticmethod
    def _build_source_list(chunks: List[Dict[str, Any]]) -> List[str]:
        """
        Build deduplicated source strings: "filename (Page N)" or just "filename".
        """
        seen: set = set()
        sources: List[str] = []
        for chunk in chunks:
            meta = chunk.get("metadata", {})
            filename = meta.get("original_filename") or meta.get("filename", "unknown")
            page_num = meta.get("page_number")
            section = meta.get("section", "")

            label = str(filename)
            if page_num:
                label += f" (Page {page_num})"
            if section and section not in ("Document Start", filename):
                label += f" [{section}]"

            if label not in seen:
                seen.add(label)
                sources.append(label)
        return sources

    # ── Post-processing ───────────────────────
    @staticmethod
    def _post_process(raw: str) -> tuple:
        """
        1. Strip <think>…</think> blocks (Qwen3/DeepSeek chain-of-thought)
        2. Extract CONFIDENCE: HIGH|MEDIUM|LOW
        Returns (answer, thought, confidence)
        """
        thought = ""
        think_match = re.search(r'<think>(.*?)</think>', raw, re.DOTALL | re.IGNORECASE)
        if think_match:
            thought = think_match.group(1).strip()
            raw = raw[:think_match.start()] + raw[think_match.end():]

        raw = raw.strip()

        confidence = None
        conf_match = re.search(r'CONFIDENCE:\s*(HIGH|MEDIUM|LOW)', raw, re.IGNORECASE)
        if conf_match:
            confidence = conf_match.group(1).upper()
            raw = raw[: conf_match.start()].strip()

        return raw, thought, confidence

    # ── Ollama Client with Retry ──────────────
    def _call_ollama_with_retry(
        self,
        prompt: str,
        max_tokens: int = 2048,
        temperature: float = 0.05,
        retries: int = 3,
    ) -> str:
        """Call Ollama with exponential back-off retry on transient errors."""
        last_exc: Optional[Exception] = None
        for attempt in range(retries):
            try:
                return self._call_ollama(prompt, max_tokens=max_tokens, temperature=temperature)
            except Exception as exc:
                last_exc = exc
                error_str = str(exc).lower()
                # Only retry on timeout or connection errors — not on Ollama model errors
                if "timeout" in error_str or "connection" in error_str:
                    wait = 2 ** attempt  # 1s, 2s, 4s
                    logger.warning(
                        f"Ollama transient error (attempt {attempt + 1}/{retries}): {exc}. "
                        f"Retrying in {wait}s…"
                    )
                    time.sleep(wait)
                else:
                    raise
        raise last_exc  # type: ignore[misc]

    def _call_ollama(
        self,
        prompt: str,
        max_tokens: int = 2048,
        temperature: float = 0.05,
    ) -> str:
        payload = {
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_predict": max_tokens,
                "temperature": temperature,
                "top_p": 0.9,
                "repeat_penalty": 1.1,
                # Enable thinking mode for Qwen3 (ignored by other models)
                "think": True,
            },
        }
        url = f"{OLLAMA_URL.rstrip('/')}/api/generate"
        try:
            resp = requests.post(url, json=payload, timeout=180)
            resp.raise_for_status()
            data = resp.json()
            if "response" in data:
                return data["response"].strip()
            if "message" in data and "content" in data["message"]:
                return data["message"]["content"].strip()
            return "Error: Unexpected response format from Ollama."
        except requests.exceptions.Timeout:
            raise Exception(
                f"Ollama timed out after 180 s. "
                f"Consider a smaller model or reducing context size. "
                f"Current model: {OLLAMA_MODEL}"
            )
        except requests.exceptions.ConnectionError:
            raise Exception(
                f"Cannot connect to Ollama at {OLLAMA_URL}. "
                "Ensure Ollama is running with: ollama serve"
            )
        except requests.exceptions.RequestException as e:
            raise Exception(f"Ollama request failed: {e}")

    def _stream_ollama(self, prompt: str, max_tokens: int = 2048) -> Generator[str, None, None]:
        """
        Stream token-by-token from Ollama's /api/generate endpoint.
        Yields individual token strings.
        Strips <think>…</think> blocks in real-time.
        """
        payload = {
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": True,
            "options": {
                "num_predict": max_tokens,
                "temperature": 0.05,
                "top_p": 0.9,
                "repeat_penalty": 1.1,
                "think": True,
            },
        }
        url = f"{OLLAMA_URL.rstrip('/')}/api/generate"
        in_think = False
        try:
            with requests.post(url, json=payload, stream=True, timeout=180) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    token = data.get("response", "")
                    # Skip <think>…</think> blocks from streaming output
                    if "<think>" in token:
                        in_think = True
                    if in_think:
                        if "</think>" in token:
                            in_think = False
                        continue
                    if token:
                        yield token
                    if data.get("done"):
                        break
        except requests.exceptions.Timeout:
            raise Exception(f"Ollama streaming timed out. Model: {OLLAMA_MODEL}")
        except requests.exceptions.ConnectionError:
            raise Exception(f"Cannot connect to Ollama at {OLLAMA_URL}.")
        except requests.exceptions.RequestException as e:
            raise Exception(f"Ollama streaming failed: {e}")