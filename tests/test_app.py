from fastapi.testclient import TestClient
from app.main import app, documents, split_chunks, rank_chunks

client = TestClient(app)

def setup_function():
    documents.clear()

def test_health():
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"

def test_chunking():
    chunks = split_chunks("This is a test document. " * 100, 120, 20)
    assert len(chunks) > 1 and all(c.strip() for c in chunks)

def test_retrieval():
    chunks = ["Employees may work remotely two days per week.", "The office kitchen closes at six."]
    result = rank_chunks("How many days can employees work remotely?", chunks, 2)
    assert result and "remotely" in result[0]["text"]

def test_ask_without_documents():
    assert client.post("/api/ask", json={"question":"What is the policy?"}).status_code == 400

def test_upload_and_ask_txt():
    r = client.post("/api/documents", files={"file":("policy.txt", b"Employees may work remotely two days per week. Managers approve requests.", "text/plain")})
    assert r.status_code == 200
    did = r.json()["document_id"]
    a = client.post("/api/ask", json={"question":"How many days can employees work remotely?", "document_id":did})
    assert a.status_code == 200 and a.json()["sources"]
    assert "remotely" in a.json()["sources"][0]["excerpt"].lower()

def test_reject_unsupported_file():
    r = client.post("/api/documents", files={"file":("policy.docx", b"some content", "application/octet-stream")})
    assert r.status_code == 415
