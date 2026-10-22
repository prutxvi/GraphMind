"""GraphMind HTTP API. Run with: uvicorn main:app --reload"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from graphmind import __version__
from graphmind.analyze import analyse
from graphmind.chat import answer
from graphmind.config import Settings, settings as default_settings
from graphmind.extract import extract_all
from graphmind.graph import KnowledgeGraph, build_graph
from graphmind.llm import LLM, LLMError, OpenAICompatibleLLM
from graphmind.pdf import PDFError, chunk_pages, read_pages
from graphmind.store import GraphStore

log = logging.getLogger("graphmind")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

DEMO_ID = "demo"
DEMO_PATH = Path(__file__).parent / "graphmind" / "demo_graph.json"
STATIC_DIR = Path(__file__).parent / "static"


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    node_id: str | None = None


def create_app(cfg: Settings = default_settings, llm: LLM | None = None) -> FastAPI:
    if llm is None and cfg.llm_api_key:
        llm = OpenAICompatibleLLM(cfg.llm_api_key, cfg.llm_base_url, cfg.llm_model)
    if llm is None:
        log.warning("No SARVAM_API_KEY set: uploads and chat are disabled, the demo graph still renders.")

    store = GraphStore(cfg.max_graphs, cfg.graph_ttl_seconds)
    if DEMO_PATH.exists():
        demo = KnowledgeGraph.from_json(
            json.loads(DEMO_PATH.read_text()),
            meta={"filename": "Financial Crisis Inquiry Report (sample)", "demo": True},
        )
        store.add(demo, graph_id=DEMO_ID, permanent=True)

    app = FastAPI(title="GraphMind", version=__version__)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cfg.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    def require_llm() -> LLM:
        if llm is None:
            raise HTTPException(503, "No LLM configured on the server (set SARVAM_API_KEY).")
        return llm

    def get_entry(graph_id: str):
        entry = store.get(graph_id)
        if entry is None:
            raise HTTPException(404, "Graph not found. It may have expired; upload the PDF again.")
        return entry

    @app.get("/api/health")
    def health():
        return {"status": "ok", "version": __version__, "llm": llm is not None, "graphs": len(store)}

    # Plain `def` endpoints run in FastAPI's threadpool, so slow LLM calls don't block the event loop.
    @app.post("/api/graphs")
    def upload(file: UploadFile = File(...)):
        model = require_llm()
        limit = cfg.max_upload_mb * 1024 * 1024
        data = file.file.read(limit + 1)
        if len(data) > limit:
            raise HTTPException(413, f"PDF is larger than {cfg.max_upload_mb} MB.")
        try:
            pages, total_pages = read_pages(data, cfg.max_pages)
        except PDFError as exc:
            raise HTTPException(422, str(exc)) from exc

        chunks = chunk_pages(pages, cfg.chunk_chars)
        warnings = []
        if total_pages > cfg.max_pages:
            warnings.append(f"Only the first {cfg.max_pages} of {total_pages} pages were processed.")
        if len(chunks) > cfg.max_chunks:
            warnings.append(f"Document truncated to pages {chunks[0].first_page}-{chunks[cfg.max_chunks - 1].last_page}.")
            chunks = chunks[: cfg.max_chunks]

        started = time.monotonic()
        extractions = extract_all(model, chunks, cfg.extract_workers)
        failed = [e for e in extractions if e.error]
        if len(failed) == len(extractions):
            raise HTTPException(502, f"The AI could not extract a graph from this PDF ({failed[0].error}).")
        if failed:
            spans = ", ".join(f"{e.chunk.first_page}-{e.chunk.last_page}" for e in failed)
            warnings.append(f"Extraction failed for pages {spans}; those pages are not in the graph.")

        covered = {n for e in extractions if not e.error for n in range(e.chunk.first_page, e.chunk.last_page + 1)}
        kg = build_graph(
            extractions,
            [p for p in pages if p.number in covered],
            meta={
                "filename": file.filename,
                "total_pages": total_pages,
                "pages_processed": len(covered),
                "chunks": len(extractions),
                "failed_chunks": len(failed),
                "seconds": round(time.monotonic() - started, 1),
                "warnings": warnings,
            },
        )
        graph_id = store.add(kg)
        log.info("graph %s: %d nodes, %d edges from %s", graph_id[:6], len(kg.nodes), len(kg.edges), file.filename)
        return {"graph_id": graph_id, **kg.to_json()}

    @app.get("/api/graphs/{graph_id}")
    def get_graph(graph_id: str):
        return {"graph_id": graph_id, **get_entry(graph_id).graph.to_json()}

    @app.post("/api/graphs/{graph_id}/chat")
    def chat(graph_id: str, req: ChatRequest):
        entry = get_entry(graph_id)
        model = require_llm()
        try:
            return answer(model, entry.graph, entry.retriever, req.message, req.node_id)
        except LLMError as exc:
            raise HTTPException(502, str(exc)) from exc

    @app.get("/api/graphs/{graph_id}/analysis")
    def analysis(graph_id: str):
        entry = get_entry(graph_id)
        if not entry.graph.nodes:
            raise HTTPException(422, "Graph is empty.")
        if entry.analysis is None:
            entry.analysis = analyse(llm, entry.graph)
        return entry.analysis

    if STATIC_DIR.exists():
        app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

        @app.get("/{full_path:path}")
        def spa(full_path: str):
            target = (STATIC_DIR / full_path).resolve()
            if target.is_file() and STATIC_DIR.resolve() in target.parents:
                return FileResponse(target)
            return FileResponse(STATIC_DIR / "index.html")

    return app


app = create_app()
