# Architecture

How a filing flows through Footnote, and where each part of it lives.

## Pipeline

```
PDF ─► pdftext: the filing's own table of contents + printed→PDF page offset
        │                                        ─► ~10 sections (≈60 of 460 pages)
        ▼
extract: fixed-field prompt per section, ~9,000-character chunks, 4 in parallel
        │                                        ─► ≈22 model calls per filing
        ▼
ingest.Normaliser: verify each quote on its page ─► entities by DIN/CIN/SEBI ─► facts
        │            raw extraction saved ─► `--relink` rebuilds everything with no model calls
        ▼
report: rule-based flags · headline · connection map · lists
chat:   TF-IDF over the filing's facts and pages ─► cited answer
        │
        ▼
FastAPI (main.py) ─► React UI (search, filing page, entity page, add, method) + pdf.js viewer
```

## Backend (`backend/`)

| File | Job |
|---|---|
| `footnote/config.py` | settings from the environment: LLM endpoint and model, data directory, upload cap, chunk size, worker count, flag thresholds |
| `footnote/llm.py` | OpenAI-compatible client, `x-opencode-session` header, `with_session()`, strips ` thinking` |
| `footnote/pdftext.py` | page text, table-of-contents parsing, page-offset vote, section location, related-party note fallback |
| `footnote/extract.py` | per-section prompt specs, chunk jobs, parallel run, JSON repair, amount units (lakh / million / crore) |
| `footnote/ingest.py` | `Ingestor` (progress, errors, saves extraction), `Normaliser` (facts), `verify()`, `redact()`, `relink()`, CLI |
| `footnote/store.py` | SQLite: filings, pages, entities, entity_keys, facts, extractions; name normalisation |
| `footnote/report.py` | `FilingReport`: flags, headline, graph, lists; `entity_report()` for cross-filing pages |
| `footnote/chat.py` | per-filing TF-IDF indexes, numbered sources, citation filtering |
| `footnote/retrieve.py` | small TF-IDF index, no embedding API |
| `main.py` | the HTTP API, and static SPA and PDF serving |
| `tests/` | 16 tests on hand-built PDFs and a `FakeLLM` |

## API

| Method | Path | What |
|---|---|---|
| GET | `/api/health` | version, whether an LLM is present, whether uploads are on |
| GET | `/api/filings` | cards: company, headline, flag summary |
| GET | `/api/filings/{id}` | the full report: flags, graph, lists |
| GET | `/api/filings/{id}/status` | live ingest progress |
| GET | `/api/filings/{id}/pdf`, `/pages/{n}` | the PDF, and the text of one page |
| POST | `/api/filings` | upload; ingest runs in a background thread |
| POST | `/api/filings/{id}/chat` | a cited answer about that filing |
| GET | `/api/entities/{id}` | everywhere a person or company appears |
| GET | `/api/search?q=` | filings and entities by name, DIN, CIN or registration |

## Frontend (`frontend/src/`)

`App.jsx` (shell, search, theme, lazy PDF viewer) · `nav.js` + `router.jsx` (a 28-line History
router — five routes do not justify a dependency) · `context.js` (viewer context, severity
labels) · `ui.jsx` (Icon, Cite, Verified, Skeleton) · `MapView.jsx` (deterministic connection
map) · `PdfViewer.jsx` (pdf.js plus quote highlighting) · `pages/` Home, Filing, Entity, Add,
Method · `styles.css` (design tokens, light and dark).

Build output: the main bundle is 238 kB (75 kB gzip). The pdf.js viewer chunk (338 kB) is
lazy-loaded, so a visitor who never opens a page never downloads it.

## Deploy shape

One service: Vite builds into `backend/static`, and FastAPI serves both. `railway.json` and
`nixpacks.toml` (Node 20 + Python 3.12) are included. Set `ALLOW_UPLOADS=0` for a public
read-only site that serves only filings already read.

## Design rules that shaped the code

- **No model decides what is suspicious.** Extraction uses a model; flags are fixed rules over
  cited facts, so a flag can be argued with by reading its page.
- **No vector database, no embedding API.** TF-IDF over the filing's own text is enough for
  questions about one document, and it costs nothing to run.
- **Raw extraction is kept**, so rule and matching fixes are re-run with `--relink` and cost
  no model calls.
- **Every stored line keeps its page and quote**, and a quote that cannot be found on its page
  is marked unverified rather than dropped or trusted.
