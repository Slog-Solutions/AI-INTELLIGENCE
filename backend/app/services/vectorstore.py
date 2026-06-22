import math
from typing import Any, List

import chromadb
from sentence_transformers import SentenceTransformer

from ..config import VECTOR_DIR


class SentenceTransformerEmbeddingFunction:
    """Sentence-transformer based embedding function for offline RAG."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model = SentenceTransformer(model_name)
        self.dimensions = self.model.get_sentence_embedding_dimension()

    @staticmethod
    def name() -> str:
        return "sentence_transformer"

    def __call__(self, input: List[str]) -> List[List[float]]:
        return self.model.encode(input).tolist()

    def embed_query(self, input: Any) -> List[List[float]]:
        if isinstance(input, str):
            return self.model.encode([input]).tolist()
        return self.model.encode(input).tolist()

    def embed_documents(self, input: List[str]) -> List[List[float]]:
        return self.model.encode(input).tolist()


class VectorStore:
    def __init__(self, collection_name: str = "atip_documents"):
        self.embedding_function = SentenceTransformerEmbeddingFunction()
        self.client = chromadb.PersistentClient(path=str(VECTOR_DIR))
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            embedding_function=self.embedding_function,
            metadata={"hnsw:space": "cosine"},
        )

    def add_documents(self, texts: List[str], metadatas: List[dict], ids: List[str]):
        if not texts:
            return
        self.collection.upsert(documents=texts, metadatas=metadatas, ids=ids)

    def query(self, query_text: str, n_results: int = 5):
        count = self.collection.count()
        if count == 0:
            return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}
        results = self.collection.query(query_texts=[query_text], n_results=min(n_results, count))
        return results

    def count(self) -> int:
        return self.collection.count()
