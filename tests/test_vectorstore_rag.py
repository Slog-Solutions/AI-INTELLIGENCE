from backend.app.services.rag_engine import RAGEngine
from backend.app.services.vectorstore import VectorStore


def test_chromadb_insert_embedding_and_similarity_search():
    vector_store = VectorStore(collection_name="validation_vectorstore")
    vector_store.add_documents(
        texts=[
            "Alpha unit marksmanship training score improved to 91 percent.",
            "Fuel stores were inspected at depot seven.",
        ],
        metadatas=[
            {"filename": "training.txt", "citation": "training.txt#chunk-1"},
            {"filename": "logistics.txt", "citation": "logistics.txt#chunk-1"},
        ],
        ids=["validation-training", "validation-logistics"],
    )

    results = vector_store.query("marksmanship score", n_results=1)
    assert results["ids"][0]
    assert results["documents"][0][0]
    assert results["metadatas"][0][0]["filename"] == "training.txt"


def test_ollama_native_response_parsing(monkeypatch):
    class DummyResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"response": "Validated response"}

    def fake_post(url, json, timeout):
        assert url.endswith("/api/generate")
        assert json["model"] == "qwen3"
        assert json["stream"] is False
        return DummyResponse()

    monkeypatch.setattr("backend.app.services.rag_engine.requests.post", fake_post)
    assert RAGEngine(VectorStore(collection_name="validation_ollama")).call_ollama("Say OK") == "Validated response"


def test_rag_pipeline_returns_answer_and_source_citations(client, auth_headers, monkeypatch):
    monkeypatch.setattr(
        "backend.app.services.rag_engine.RAGEngine.call_ollama",
        lambda self, prompt: "Training performance answer from local validation model.",
    )
    headers = auth_headers("instructor_alpha", "Inst123!")

    with open("samples/training_performance.csv", "rb") as sample:
        upload = client.post(
            "/upload/file",
            headers=headers,
            data={"category": "Training", "source": "Automated Test"},
            files={"file": ("training_performance.csv", sample, "text/csv")},
        )
    assert upload.status_code == 200, upload.text

    response = client.post("/chat/query", headers=headers, json={"query": "What training performance is available?"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert "Training performance answer" in body["answer"]
    assert body["sources"]
    assert any("training_performance" in source for source in body["sources"])
