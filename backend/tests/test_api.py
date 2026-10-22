import pytest
from fastapi.testclient import TestClient

from graphmind.config import Settings
from graphmind.store import GraphStore
from graphmind.graph import KnowledgeGraph
from main import create_app

from conftest import FakeLLM


@pytest.fixture
def client(fake_llm):
    return TestClient(create_app(Settings(chunk_chars=120, max_upload_mb=1), llm=fake_llm))


def upload(client, pdf_bytes):
    res = client.post("/api/graphs", files={"file": ("crisis.pdf", pdf_bytes, "application/pdf")})
    assert res.status_code == 200, res.text
    return res.json()


def test_health(client):
    assert client.get("/api/health").json()["llm"] is True


def test_demo_graph_is_available(client):
    data = client.get("/api/graphs/demo").json()
    assert len(data["nodes"]) > 10 and data["meta"]["demo"] is True


def test_upload_builds_graph_with_provenance(client, pdf_bytes):
    data = upload(client, pdf_bytes)
    assert len(data["graph_id"]) >= 20
    assert data["meta"]["pages_processed"] == 3 and data["meta"]["warnings"] == []
    lehman = next(n for n in data["nodes"] if n["id"] == "Lehman Brothers")
    assert lehman["pages"] == [1, 2]


def test_uploads_are_isolated(client, pdf_bytes):
    a, b = upload(client, pdf_bytes), upload(client, pdf_bytes)
    assert a["graph_id"] != b["graph_id"]
    assert client.get(f"/api/graphs/{a['graph_id']}").status_code == 200
    # A second upload must not replace the first, and the demo is untouched.
    assert len(client.get("/api/graphs/demo").json()["nodes"]) > 10


def test_chat_returns_page_citations(client, pdf_bytes):
    gid = upload(client, pdf_bytes)["graph_id"]
    res = client.post(f"/api/graphs/{gid}/chat", json={"message": "Who sold credit default swaps?"}).json()
    assert res["focused_node"] == "AIG"
    assert res["citations"] and res["citations"][0]["id"] in res["reply"]
    assert all("page" in c for c in res["citations"])


def test_chat_ignores_citations_to_unknown_sources(pdf_bytes):
    llm = FakeLLM(__import__("conftest").EXTRACTIONS, chat_reply="Made up [S99].")
    c = TestClient(create_app(Settings(chunk_chars=120), llm=llm))
    gid = upload(c, pdf_bytes)["graph_id"]
    assert c.post(f"/api/graphs/{gid}/chat", json={"message": "AIG"}).json()["citations"] == []


def test_unknown_graph_is_404(client):
    assert client.post("/api/graphs/nope/chat", json={"message": "hi"}).status_code == 404


def test_rejects_non_pdf_and_oversized(client):
    assert client.post("/api/graphs", files={"file": ("a.pdf", b"not a pdf", "application/pdf")}).status_code == 422
    big = b"%PDF" + b"0" * (1024 * 1024 + 10)
    assert client.post("/api/graphs", files={"file": ("a.pdf", big, "application/pdf")}).status_code == 413


def test_upload_without_llm_is_503(pdf_bytes):
    c = TestClient(create_app(Settings(llm_api_key=None)))
    assert c.post("/api/graphs", files={"file": ("a.pdf", pdf_bytes, "application/pdf")}).status_code == 503
    assert c.get("/api/graphs/demo").status_code == 200


def test_analysis(client, pdf_bytes):
    gid = upload(client, pdf_bytes)["graph_id"]
    data = client.get(f"/api/graphs/{gid}/analysis").json()
    assert data["total_nodes"] >= 4 and data["hub_nodes"][0]["connections"] >= 1
    assert data["ai_summary"]


def test_store_evicts_oldest_and_expires():
    now = [0.0]
    store = GraphStore(max_graphs=2, ttl_seconds=10, clock=lambda: now[0])
    store.add(KnowledgeGraph(), "demo", permanent=True)
    a = store.add(KnowledgeGraph())
    b = store.add(KnowledgeGraph())
    c = store.add(KnowledgeGraph())
    assert store.get(a) is None and store.get(b) and store.get(c)
    now[0] = 11
    assert store.get(b) is None and store.get("demo") is not None
