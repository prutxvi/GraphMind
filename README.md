# 🧠 GraphMind

**Turn a PDF into a 3D knowledge graph you can question, where every answer is cited back to a page.**

Upload a report, paper or policy document. GraphMind reads every page, extracts the people, organisations, concepts and events in it, merges duplicates, and draws the result as an interactive 3D graph. Ask a question and the answer comes from graph facts and the source text, with `[S1] · p.12` citations you can click.

## How it works

```
PDF ──► pages ──► page-aware chunks ──► LLM extraction (parallel, per chunk)
                                              │
                    merge entities by name + aliases ("Federal Reserve" = "the Fed")
                    pages per entity = where its name actually appears in the text
                    each relation keeps a quote, verified verbatim against the PDF
                                              │
question ──► TF-IDF over entities + pages ──► facts + passages as numbered sources
                                              │
                                    LLM answers citing [S#] ──► page citations
```

What makes it more than "send a PDF to a chatbot":

- **Whole-document extraction.** Every page is processed in ~5,000-character chunks, not just the first few thousand characters. Limits are explicit and reported back (`MAX_PAGES`, `MAX_CHUNKS`).
- **Entity resolution across chunks.** The same entity mentioned on page 3 and page 40 becomes one node. Only proper-noun aliases are trusted to merge, so a stray "bank" alias can't glue two banks together.
- **Provenance you can check.** A node's page list comes from searching the text, not from the model. Relation quotes are checked against the source and marked `verified: false` if the model invented them.
- **Grounded chat.** Answers may only use the numbered sources, and citations to sources that don't exist are dropped.
- **Per-upload graphs.** Each upload gets its own unguessable ID, so two users never overwrite each other.

## Quick start

Requires Python 3.10+ and Node 18+.

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env          # add your SARVAM_API_KEY
uvicorn main:app --reload     # http://127.0.0.1:8000/docs

# Frontend (second terminal)
cd frontend
npm install
npm run dev                   # http://localhost:5173
```

Without an API key, the bundled sample graph (Financial Crisis Inquiry Report) still loads. Upload and chat return a clear 503 until you add a key.

The LLM is any OpenAI-compatible chat endpoint. It defaults to Sarvam (`gemma4`); set `LLM_BASE_URL` and `LLM_MODEL` to use another provider.

## API

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/graphs` | Upload a PDF (`file` form field). Returns `graph_id`, nodes, links and processing `meta` (pages processed, warnings). |
| `GET` | `/api/graphs/{id}` | Fetch a graph. `demo` is the bundled sample. |
| `POST` | `/api/graphs/{id}/chat` | `{"message": "...", "node_id": null}` → `reply`, `citations[]`, `focused_node`. |
| `GET` | `/api/graphs/{id}/analysis` | Hub and bridge nodes, clusters, isolated concepts, plus an AI summary. |
| `GET` | `/api/health` | Liveness and whether an LLM is configured. |

## Configuration

All settings are environment variables; see [`backend/.env.example`](backend/.env.example). The ones you're most likely to touch:

| Variable | Default | |
| --- | --- | --- |
| `SARVAM_API_KEY` | none | Required for upload and chat. |
| `CORS_ORIGINS` | `localhost:5173` | Comma-separated. Not needed when the backend serves the built frontend. |
| `MAX_CHUNKS` | `40` | Caps LLM calls (and cost) per upload. |
| `EXTRACT_WORKERS` | `4` | Parallel LLM calls. Lower it if you hit rate limits. |

## Tests

```bash
cd backend && pytest
```

The suite runs on a fake LLM and hand-built PDFs, so it needs no network or API key. It covers chunking, cross-chunk merging, page attribution, quote verification, retrieval ranking, JSON repair, upload isolation, citations and the store's expiry. CI runs it on Python 3.10 and 3.12, along with the frontend lint and build.

## Limitations

These are known and intentional for now:

- Graphs live in server memory (default: 50 graphs, 6-hour expiry) and are lost on restart.
- Scanned, image-only PDFs need OCR first.
- Retrieval is TF-IDF, not embeddings. That's fast and free, but it misses pure paraphrases ("bankrupt" vs "insolvency").
- Entity merging is name/alias-based. Two different people with the same name will merge.

## Deploy

One service: the frontend is built into `backend/static` and served by FastAPI. Railway config is included (`railway.json`, `nixpacks.toml`); see [DEPLOYMENT.md](DEPLOYMENT.md) for other options.

## Stack

FastAPI · NetworkX · pypdf · React 19 · Vite · react-force-graph-3d (Three.js)

## License

MIT, see [LICENSE](LICENSE).
