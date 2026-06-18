import hashlib
import math
from typing import Any

import chromadb

from ..config import VECTOR_DIR


class HashEmbeddingFunction:
    """Small deterministic offline embedding function for validation and local use."""

    def __init__(self, dimensions: int = 384):
        self.dimensions = dimensions

    @staticmethod
    def name() -> str:
        return "default"

    def __call__(self, input):
        return [self.embed(text) for text in input]

    def embed_query(self, input: Any) -> list[list[float]]:
        if isinstance(input, str):
            return [self.embed(input)]
        return [self.embed(text) for text in input]

    def embed_documents(self, input: list[str]) -> list[list[float]]:
        return [self.embed(text) for text in input]

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        tokens = [token.strip(".,:;!?()[]{}\"'").lower() for token in text.split()]
        for token in tokens:
            if not token:
                continue
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]


class VectorStore:
    def __init__(self, collection_name: str = "atip_documents"):
        self.embedding_function = HashEmbeddingFunction()
        self.client = chromadb.PersistentClient(path=str(VECTOR_DIR))
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            embedding_function=self.embedding_function,
            metadata={"hnsw:space": "cosine"},
        )

    def add_documents(self, texts: list[str], metadatas: list[dict], ids: list[str]):
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
