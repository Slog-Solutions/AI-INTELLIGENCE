import requests
import json
import logging
from typing import List, Dict, Any
from flashrank import Ranker, RerankRequest
from ..config import OLLAMA_URL, OLLAMA_MODEL

logger = logging.getLogger(__name__)

class RAGEngine:
    def __init__(self, vector_store):
        self.vector_store = vector_store
        self.ranker = Ranker(model_name="ms-marco-MiniLM-L-12-v2", cache_dir="/tmp/flashrank_cache")

    def build_prompt(self, query: str, sources: List[Dict[str, Any]]) -> str:
        context_parts = []
        for i, src in enumerate(sources):
            filename = src["metadata"].get("original_filename") or src["metadata"].get("filename", "unknown")
            page_number = src["metadata"].get("page_number")
            source_info = f"SOURCE {i+1}: {filename}"
            if page_number:
                source_info += f" (Page {page_number})"
            context_parts.append(f"--- {source_info} ---\n{src['document']}")
        
        context = "\n\n".join(context_parts)
        
        return (
            "You are the Army Training Intelligence Platform (ATIP) Assistant, a highly specialized military intelligence AI. "
            "Your goal is to provide accurate, concise, and actionable insights based ONLY on the provided training reports and documents.\n\n"
            "INSTRUCTIONS:\n"
            "1. Use the provided context to answer the user's query.\n"
            "2. If the answer is not in the context, explicitly state that the information is not available in the current document set.\n"
            "3. Always cite the specific source filenames and page numbers (if available) used in your answer, e.g., [SOURCE 1: document.pdf (Page 5)].\n"
            "4. Format your response using professional military terminology where appropriate.\n"
            "5. If numbers or trends are requested, extract them precisely from the context.\n"
            "6. Provide a confidence score for your answer (e.g., 'Confidence: High', 'Confidence: Medium', 'Confidence: Low').\n\n"
            f"CONTEXT:\n{context}\n\n"
            f"USER QUERY: {query}\n\n"
            "INTELLIGENCE REPORT:"
        )

    def generate_summary_prompt(self, filename: str, content: str) -> str:
        return (
            f"Analyze the following content from the document '{filename}' and provide a structured military intelligence summary.\n\n"
            "CONTENT:\n"
            f"{content[:4000]}\n\n"
            "Provide the summary in the following format:\n"
            "- **What this report contains**: (Brief overview)\n"
            "- **Key insights**: (3-5 bullet points)\n"
            "- **Important numbers**: (Specific data points)\n"
            "- **Trends detected**: (Any patterns observed)\n"
            "- **Recommendations**: (Actionable advice)"
        )

    def query(self, query: str) -> Dict[str, Any]:
        try:
            results = self.vector_store.query(query, n_results=20)
            if not results or not results.get("ids") or not results["ids"][0]:
                return {"answer": "I could not find any relevant documents in the intelligence database to answer your question.", "sources": []}

            documents_for_reranking = []
            for idx in range(len(results["ids"][0])):
                doc_text = results["documents"][0][idx]
                metadata = results["metadatas"][0][idx]
                documents_for_reranking.append({"text": doc_text, "meta": metadata})
            
            rerank_request = RerankRequest(query=query, passages=documents_for_reranking)
            reranked_results = self.ranker.rerank(rerank_request)
            top_n_documents = reranked_results[:7]

            final_sources = []
            unique_source_identifiers = set()
            for doc in top_n_documents:
                doc_text = doc["text"]
                metadata = doc["meta"]
                final_sources.append({"document": doc_text, "metadata": metadata})
                filename = metadata.get("original_filename") or metadata.get("filename", "unknown")
                page_number = metadata.get("page_number")
                source_identifier = f"{filename}"
                if page_number:
                    source_identifier += f" (Page {page_number})"
                unique_source_identifiers.add(source_identifier)
            
            prompt = self.build_prompt(query, final_sources)
            response_text = self.call_ollama(prompt)
            return {"answer": response_text, "sources": list(unique_source_identifiers)}
        except Exception as e:
            logger.error(f"RAG Query Error: {str(e)}")
            return {"answer": f"Internal Intelligence Engine Error: {str(e)}", "sources": []}

    def summarize_document(self, filename: str, content: str) -> str:
        try:
            prompt = self.generate_summary_prompt(filename, content)
            return self.call_ollama(prompt)
        except Exception as e:
            logger.error(f"Summarization Error: {str(e)}")
            return "Failed to generate AI summary."

    def call_ollama(self, prompt: str) -> str:
        payload = {
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_predict": 1024,
                "temperature": 0.1,
                "top_p": 0.9
            },
        }
        url = f"{OLLAMA_URL.rstrip('/')}/api/generate"
        try:
            resp = requests.post(url, json=payload, timeout=90)
            resp.raise_for_status()
            data = resp.json()
            if "response" in data:
                return data["response"].strip()
            elif "message" in data and "content" in data["message"]:
                return data["message"]["content"].strip()
            return "Error: Unexpected response format from Ollama."
        except requests.exceptions.RequestException as e:
            logger.error(f"Ollama Connection Error: {str(e)}")
            raise Exception(f"Failed to connect to Ollama service at {OLLAMA_URL}. Ensure Ollama is running.")
