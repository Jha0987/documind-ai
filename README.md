# DocuMind AI

**Document Q&A prototype with source-aware retrieval and optional Gemini answer generation.**

> **Status: MVP / in progress.** This version uses lexical retrieval, not embedding-based semantic search. PostgreSQL, pgvector, embeddings, and a formal evaluation benchmark are planned features, not implemented features.

## MVP features
- Upload text-based PDF and UTF-8 TXT files (8 MB maximum).
- Extract and clean text, split it into overlapping chunks.
- Retrieve potentially relevant passages with lexical token matching.
- Return source excerpts and heuristic relevance scores.
- Optional Gemini answer generation grounded in retrieved excerpts.
- Basic validation, API error handling, browser UI, and automated tests.
- Swagger documentation at `/docs`.

## Architecture
```text
Browser UI -> FastAPI
              |-- /api/documents: PDF/TXT extraction -> chunking -> in-memory store
              |-- /api/ask: lexical retrieval -> source excerpts -> optional Gemini
              |-- /api/documents (GET/DELETE)
              \-- /health
```

## Requirements
Python 3.10+.

## Run on Windows PowerShell
```powershell
git clone https://github.com/YOUR_USERNAME/documind-ai.git
cd documind-ai
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload
```
Open http://127.0.0.1:8000 for the app and http://127.0.0.1:8000/docs for API docs.

If PowerShell blocks activation:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

## Optional Gemini setup
Create a Gemini API key through Google's official AI Studio/API console, then put it in `.env`:
```env
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-2.5-flash
```
Restart the server. Without a key, upload/retrieval still work and the app returns source excerpts rather than synthesized answers. If the model call fails, it falls back to retrieval-only mode. Model availability and quotas can change; configure a supported model for your account. Never commit `.env` or expose keys in frontend code.

## Tests
```powershell
pytest -q
```

## API
- `GET /health`
- `POST /api/documents` — multipart field `file`; PDF/TXT only
- `GET /api/documents` — list documents in this process
- `DELETE /api/documents/{document_id}`
- `POST /api/ask` — JSON example:
```json
{"question":"What is the remote work policy?","document_id":null,"top_k":3}
```

## Limitations
- Documents are held in memory and disappear when the server restarts.
- Not production-hardened; no authentication or persistent storage.
- Scanned/image-only PDFs need OCR, which is not included.
- Lexical matching can miss semantically related passages.
- Scores are heuristic, not probabilities.
- LLM outputs can be incorrect; verify citations.
- No PostgreSQL, pgvector, embeddings, or formal AI evaluation benchmark yet.

## Roadmap
1. Add embeddings and semantic retrieval.
2. Persist documents/chunks/metadata in PostgreSQL + pgvector.
3. Build a curated question-answer evaluation dataset.
4. Measure Recall@k, answer relevance, and citation support.
5. Add unsupported-question tests, persistence, authentication, and deployment hardening.

## Resume guidance
Only claim features you have run and verified. After testing this MVP, an accurate entry could be:

**DocuMind AI — Document Q&A Prototype | Python, FastAPI, PDF Processing, Gemini API (optional)**
- Built a FastAPI application that extracts and chunks PDF/TXT content and retrieves relevant source passages for user questions.
- Returned source excerpts and heuristic relevance scores to make retrieval results inspectable.
- Added optional Gemini answer generation based on retrieved context with a retrieval-only fallback.

Adjust these bullets to match what you actually run and configure.

## License
MIT
