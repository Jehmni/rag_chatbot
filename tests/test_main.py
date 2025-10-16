import sys
from pathlib import Path

# Insert project root so tests can import package modules
root = Path(__file__).parents[1].resolve()
sys.path.insert(0, str(root))  # noqa: E402 (we insert project root for imports)

import pytest
from fastapi.testclient import TestClient

from app.main import app


class DummyRAG:
    def __init__(self, cfg, session=None):
        pass

    async def answer_query(self, query: str):
        return "dummy answer", ["doc1", "doc2"]


@pytest.fixture(autouse=True)
def override_rag_manager(monkeypatch):
    # Replace RAGManager in app.state with dummy implementation for tests
    # Set both clients_config and rag_managers so endpoints work
    app.state.clients_config = {"example_client": {}}
    app.state.rag_managers = {"example_client": DummyRAG({})}


def test_health():
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_clients():
    client = TestClient(app)
    r = client.get("/clients")
    assert r.status_code == 200
    assert "example_client" in r.json()["clients"]


def test_chat():
    client = TestClient(app)
    r = client.post("/chat/example_client", json={"query": "hello"})
    assert r.status_code == 200
    data = r.json()
    assert data["answer"] == "dummy answer"
    assert isinstance(data["sources"], list)
