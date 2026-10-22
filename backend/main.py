"""Footnote HTTP API. Run with: uvicorn main:app --reload"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from footnote import __version__
from footnote.chat import Indexes, answer
from footnote.config import Settings, settings as default_settings
from footnote.ingest import Ingestor
from footnote.llm import LLM, LLMError, OpenAICompatibleLLM
from footnote.report import FilingReport, entity_report
from footnote.store import Store

log = logging.getLogger("footnote")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

STATIC_DIR = Path(__file__).parent / "static"


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


def create_app(cfg: Settings = default_settings, llm: LLM | None = None, store: Store | None = None) -> FastAPI:
    if llm is None and cfg.llm_api_key:
        llm = OpenAICompatibleLLM(cfg.llm_api_key, cfg.llm_base_url, cfg.llm_model)
    if llm is None:
        log.warning("No LLM_API_KEY set: reading existing filings works; uploads and questions are disabled.")
    store = store or Store(cfg.db_path)
    ingestor = Ingestor(store, llm, cfg) if llm else None
    indexes = Indexes()

    # A filing left mid-way by a restart will never finish; mark it so the UI can say so.
    for f in store.filings():
        if f["status"] in ("queued", "processing"):
            store.update_filing(f["id"], status="error", progress={**f["progress"], "stage": "error",
                                                                   "message": "Interrupted by a server restart. Upload again."})

    app = FastAPI(title="Footnote", version=__version__)
    app.add_middleware(CORSMiddleware, allow_origins=cfg.cors_origins, allow_methods=["GET", "POST"],
                       allow_headers=["Content-Type"])

    def ready_report(filing_id: str) -> FilingReport:
        filing = store.filing(filing_id)
        if not filing:
            raise HTTPException(404, "Filing not found.")
        if filing["status"] != "ready":
            raise HTTPException(409, f"Filing is {filing['status']}.")
        return FilingReport(store, filing, cfg)

    @app.get("/api/health")
    def health():
        return {"status": "ok", "version": __version__, "llm": llm is not None, "uploads": bool(ingestor and cfg.allow_uploads)}

    @app.get("/api/filings")
    def list_filings():
        out = []
        for f in store.filings():
            if f["status"] == "ready":
                s = FilingReport(store, f, cfg).summary()
                out.append({k: s[k] for k in ("id", "company", "headline", "meta", "counts", "promoter_holding_pct")}
                           | {"flags": [{k: fl[k] for k in ("id", "severity", "label", "value")} for fl in s["flags"]]})
        return out

    @app.get("/api/filings/{filing_id}")
    def get_filing(filing_id: str):
        return ready_report(filing_id).full()

    @app.get("/api/filings/{filing_id}/status")
    def status(filing_id: str):
        f = store.filing(filing_id)
        if not f:
            raise HTTPException(404, "Filing not found.")
        return {"id": f["id"], "status": f["status"], "progress": f["progress"], "company": f["company"]}

    @app.get("/api/filings/{filing_id}/pdf")
    def pdf(filing_id: str):
        f = store.filing(filing_id)
        if not f or not Path(f["pdf_path"]).exists():
            raise HTTPException(404, "PDF not found.")
        return FileResponse(f["pdf_path"], media_type="application/pdf")

    @app.get("/api/filings/{filing_id}/pages/{number}")
    def page(filing_id: str, number: int):
        text = store.page(filing_id, number)
        if text is None:
            raise HTTPException(404, "Page not found.")
        return {"number": number, "text": text}

    @app.post("/api/filings")
    def upload(file: UploadFile = File(...)):
        if not ingestor or not cfg.allow_uploads:
            raise HTTPException(503, "Uploads are disabled on this server.")
        limit = cfg.max_upload_mb * 1024 * 1024
        data = file.file.read(limit + 1)
        if len(data) > limit:
            raise HTTPException(413, f"PDF is larger than {cfg.max_upload_mb} MB.")
        if not data.startswith(b"%PDF"):
            raise HTTPException(422, "File is not a PDF.")
        with NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(data)
        stem = Path(file.filename or "filing").stem
        src = Path(tmp.name).with_name(f"{stem}.pdf")
        Path(tmp.name).rename(src)
        filing_id = ingestor.add_pdf(src)
        src.unlink(missing_ok=True)
        indexes.drop(filing_id)
        threading.Thread(target=ingestor.run, args=(filing_id,), daemon=True).start()
        return {"id": filing_id}

    @app.post("/api/filings/{filing_id}/chat")
    def chat(filing_id: str, req: ChatRequest):
        report = ready_report(filing_id)
        if llm is None:
            raise HTTPException(503, "Questions are disabled: no LLM configured on the server.")
        try:
            return answer(llm, store, report, indexes, req.message)
        except LLMError as exc:
            raise HTTPException(502, str(exc)) from exc

    @app.get("/api/entities/{entity_id}")
    def entity(entity_id: int):
        rep = entity_report(store, entity_id)
        if not rep:
            raise HTTPException(404, "Not found.")
        return rep

    @app.get("/api/search")
    def search(q: str):
        if len(q.strip()) < 2:
            return {"filings": [], "entities": []}
        return store.search(q)

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
