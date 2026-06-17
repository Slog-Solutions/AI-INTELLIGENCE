import requests
from ..config import OLLAMA_URL, OLLAMA_MODEL

class RAGEngine:
    def __init__(self, vector_store):
        self.vector_store = vector_store

    def build_prompt(self, query: str, sources: list[dict]) -> str:
        context = "\n\n".join([f"Source: {src['metadata'].get('filename', 'unknown')}\n{src['document']}" for src in sources])
        return f"Use the following context to answer the question. Cite source filenames.\n\nContext:\n{context}\n\nQuestion: {query}\nAnswer:"

    def query(self, query: str) -> dict:
        results = self.vector_store.query(query, n_results=4)
        documents = []
        sources = []
        for idx, doc_id in enumerate(results.get("ids", [[]])[0]):
            metadata = results["metadatas"][0][idx]
            documents.append({"document": results["documents"][0][idx], "metadata": metadata})
            citation = metadata.get("citation") or metadata.get("filename", "unknown")
            if citation not in sources:
                sources.append(citation)
        if not documents:
            return {"answer": "No relevant documents were found for this question.", "sources": []}
        prompt = self.build_prompt(query, documents)
        response_text = self.call_ollama(prompt)
        return {"answer": response_text, "sources": sources}

    def call_ollama(self, prompt: str) -> str:
        payload = {
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_predict": 512,
                "temperature": 0.2,
            },
        }
        url = f"{OLLAMA_URL.rstrip('/')}/api/generate"
        resp = requests.post(url, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        if "response" in data:
            return data["response"]
        if "results" in data:
            return data.get("results", [{}])[0].get("content", "")
        if "choices" in data:
            choice = data["choices"][0]
            return choice.get("message", {}).get("content") or choice.get("text", "")
        return ""
