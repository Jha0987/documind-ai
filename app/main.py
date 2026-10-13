import os, re, uuid
from io import BytesIO
from pathlib import Path
from collections import Counter
from typing import Any
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from pypdf import PdfReader

BASE = Path(__file__).resolve().parent
MAX_BYTES = 8 * 1024 * 1024
ALLOWED = {".pdf", ".txt"}
API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
app = FastAPI(title="DocuMind AI", description="Document Q&A prototype with source-aware retrieval and optional Gemini generation.", version="0.1.0")
documents: dict[str, dict[str, Any]] = {}

class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1000)
    document_id: str | None = None
    top_k: int = Field(default=3, ge=1, le=5)

def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\x00", " ")).strip()

def split_chunks(text: str, chunk_size: int = 900, overlap: int = 120) -> list[str]:
    text = clean_text(text)
    chunks, start = [], 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        if end < len(text):
            boundary = text.rfind(" ", start + int(chunk_size * .65), end)
            if boundary > start:
                end = boundary
        part = text[start:end].strip()
        if part: chunks.append(part)
        if end >= len(text): break
        start = max(end - overlap, start + 1)
    return chunks

def tokens(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z0-9][a-zA-Z0-9_-]{1,}", text.lower())

def rank_chunks(question: str, chunks: list[str], top_k: int) -> list[dict[str, Any]]:
    q = set(tokens(question))
    if not q: return []
    scored = []
    for i, chunk in enumerate(chunks):
        ct = tokens(chunk); counts = Counter(ct)
        overlap = sum(min(counts[t], 3) for t in q)
        score = overlap / max(len(set(ct)) ** .5, 1)
        if overlap: scored.append({"chunk_index": i, "text": chunk, "score": round(score, 4)})
    return sorted(scored, key=lambda x: x["score"], reverse=True)[:top_k]

async def generate_with_gemini(question: str, sources: list[dict[str, Any]]) -> str | None:
    if not API_KEY or not sources: return None
    try:
        from google import genai
        client = genai.Client(api_key=API_KEY)
        context = "\n\n".join(f"[Source {i+1}: {s['filename']}, chunk {s['chunk_index']+1}]\n{s['text']}" for i, s in enumerate(sources))
        prompt = f"""Answer using ONLY the source excerpts below. If they do not contain enough evidence, say so. Do not invent facts. Cite sources as [1], [2], etc.
SOURCE EXCERPTS:
{context}
QUESTION: {question}"""
        result = client.models.generate_content(model=MODEL, contents=prompt)
        return result.text.strip() if getattr(result, "text", None) else None
    except Exception:
        return None

@app.get("/", include_in_schema=False)
def home(): return FileResponse(BASE / "static" / "index.html")

@app.get("/health")
def health(): return {"status": "ok", "service": "documind-ai", "llm_enabled": bool(API_KEY)}

@app.get("/api/documents")
def list_documents():
    return [{"document_id": did, "filename": d["filename"], "chunk_count": len(d["chunks"]), "character_count": d["character_count"]} for did, d in documents.items()]

@app.delete("/api/documents/{document_id}")
def delete_document(document_id: str):
    if document_id not in documents: raise HTTPException(404, "Document not found.")
    del documents[document_id]
    return {"deleted": True, "document_id": document_id}

@app.post("/api/documents")
async def upload_document(file: UploadFile = File(...)):
    filename = Path(file.filename or "upload").name
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED: raise HTTPException(415, "Only PDF and TXT files are supported.")
    data = await file.read(MAX_BYTES + 1)
    if not data: raise HTTPException(400, "The uploaded file is empty.")
    if len(data) > MAX_BYTES: raise HTTPException(413, "File is too large. Maximum size is 8 MB.")
    try:
        text = "\\n".join(p.extract_text() or "" for p in PdfReader(BytesIO(data)).pages) if suffix == ".pdf" else data.decode("utf-8-sig")
    except Exception:
        raise HTTPException(400, "Could not read this file. Check that it is a valid PDF or UTF-8 text file.")
    text = clean_text(text)
    if len(text) < 20: raise HTTPException(422, "No usable text found. Scanned/image-only PDFs need OCR, which this MVP does not include.")
    chunks = split_chunks(text); did = str(uuid.uuid4())
    documents[did] = {"filename": filename, "text": text, "chunks": chunks, "character_count": len(text)}
    return {"document_id": did, "filename": filename, "chunk_count": len(chunks), "character_count": len(text), "message": "Document processed successfully."}

@app.post("/api/ask")
async def ask_question(request: AskRequest):
    if not documents: raise HTTPException(400, "Upload a document before asking a question.")
    if request.document_id:
        if request.document_id not in documents: raise HTTPException(404, "Selected document was not found.")
        selected = {request.document_id: documents[request.document_id]}
    else: selected = documents
    found = []
    for did, doc in selected.items():
        for item in rank_chunks(request.question, doc["chunks"], request.top_k):
            found.append({**item, "document_id": did, "filename": doc["filename"]})
    sources = sorted(found, key=lambda x: x["score"], reverse=True)[:request.top_k]
    if not sources:
        return {"answer": "I couldn't find relevant passages in the uploaded documents. Try rephrasing the question or upload a document covering the topic.", "sources": [], "mode": "retrieval_only", "notice": "Lexical retrieval may miss semantically related passages."}
    generated = await generate_with_gemini(request.question, sources)
    mode = "gemini_grounded" if generated else "retrieval_only"
    answer = generated or "I found potentially relevant passages. Review the source excerpts below; this baseline does not synthesize a complete answer."
    return {"answer": answer, "sources": [{"source_number": i+1, "document_id": s["document_id"], "filename": s["filename"], "chunk_index": s["chunk_index"], "relevance_score": s["score"], "excerpt": s["text"]} for i, s in enumerate(sources)], "mode": mode, "notice": "LLM-generated answer based on retrieved excerpts; verify citations." if generated else "Lexical retrieval baseline. Configure GEMINI_API_KEY for grounded answer generation."}

app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")
