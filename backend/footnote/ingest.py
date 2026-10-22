"""Filing -> sections -> extraction -> verified facts in the store.

    python -m footnote.ingest path/to/filing.pdf [more.pdf ...]
    python -m footnote.ingest --relink [filing-id ...]   # re-link from saved extraction, no model calls
"""

from __future__ import annotations

import logging
import re
import shutil
import sys
import threading
import time
from pathlib import Path

from .config import Settings, settings as default_settings
from .extract import Job, Result, build_jobs, run_jobs, to_number, to_rupees
from .llm import LLM, OpenAICompatibleLLM
from .pdftext import locate_sections, read_pages, related_party_note
from .store import Store, looks_like_org

log = logging.getLogger(__name__)

SECTION_LABEL = {
    "general_information": "General Information",
    "management": "Our Management",
    "promoters": "Our Promoters",
    "group_companies": "Group Companies",
    "rpt_summary": "Related party transactions",
    "litigation": "Outstanding Litigation",
    "objects": "Objects of the Issue",
    "financial_summary": "Summary financials",
}


def slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.casefold()).strip("-")
    return s[:60] or "filing"


_PAN = re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")
_AADHAAR = re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b")


def redact(text: str) -> str:
    """Personal identifiers have no place in Footnote's stored text, even though the filing prints them."""
    return _AADHAAR.sub("[ID removed]", _PAN.sub("[PAN removed]", text))


def _alnum(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.casefold())


def verify(quote: str | None, page: int | None, pages: list[str], lo: int, hi: int) -> tuple[int | None, bool]:
    """Find the model's quote in the source. Returns the page it is really on and whether it was found.
    Comparison ignores spacing/punctuation because PDF tables extract with irregular whitespace."""
    if not isinstance(page, int) or not lo <= page <= hi:
        page = None
    order = [p for p in (page, *(range(lo, hi + 1))) if p]
    # Models shorten long rows with "..."; accept the quote when every part is on the same page.
    parts = [_alnum(x) for x in re.split(r"\.\.\.|…|;\s", quote or "")]
    parts = [x for x in parts if len(x) >= 6]
    if len(parts) > 1:
        for number in dict.fromkeys(order):
            text = _alnum(pages[number - 1])
            if all(x in text for x in parts):
                return number, True
        return page, False
    needle = _alnum(quote or "")
    if len(needle) < 10:
        return page, False
    for number in dict.fromkeys(order):
        if needle in _alnum(pages[number - 1]):
            return number, True
    # Long table rows are often reflowed; accept a match on the first 40 characters.
    head = needle[:40]
    for number in dict.fromkeys(order):
        if len(head) >= 20 and head in _alnum(pages[number - 1]):
            return number, True
    return page, False


def _issuer_name(pages: list[str]) -> str | None:
    for text in pages[:3]:
        m = re.search(r"^\s*([A-Z][A-Z0-9&.,()' \-]{3,80}?\s(?:LIMITED|LTD\.?))\s*$", text, re.MULTILINE)
        if m:
            return re.sub(r"\s+", " ", m.group(1)).title().replace(" Ltd.", " Limited")
    return None


class Normaliser:
    """Turns extraction results into entity rows and fact rows for one filing."""

    def __init__(self, store: Store, filing_id: str, pages: list[str]):
        self.store, self.filing_id, self.pages = store, filing_id, pages
        self.facts: list[dict] = []
        self.issuer_id: int | None = None
        self.din_by_name: dict[str, str] = {}
        self._objects_seen = False

    def entity(self, name: str, kind: str | None = None, **ids) -> int | None:
        name = (name or "").strip()
        if len(name) < 2:
            return None
        if kind == "person" and not ids.get("din"):
            ids["din"] = self.din_by_name.get(name.casefold())
        return self.store.upsert_entity(self.filing_id, name, kind, **ids)

    def fact(self, result: Result, item: dict, kind: str, subject=None, obj=None, amount=None, **attrs) -> None:
        page, ok = verify(item.get("quote"), item.get("page"), self.pages, result.job.first_page, result.job.last_page)
        self.facts.append({
            "filing_id": self.filing_id, "kind": kind, "subject_id": subject, "object_id": obj,
            "attrs": {k: v for k, v in attrs.items() if v not in (None, "", [])},
            "amount": amount, "page": page, "quote": redact(item.get("quote") or "")[:400], "verified": ok,
            "section": result.job.section,
        })

    def run(self, results: list[Result]) -> None:
        by_section: dict[str, list[Result]] = {}
        for r in results:
            if not r.error:
                by_section.setdefault(r.job.section, []).append(r)

        # People with DINs first, so later name-only mentions (e.g. in RPT tables) resolve to them.
        for key in ("general_information", "management", "promoters"):
            for r in by_section.get(key, []):
                for d in [*r.data.get("directors", []), *r.data.get("promoters", [])]:
                    if isinstance(d, dict) and d.get("din") and d.get("name"):
                        self.din_by_name[d["name"].strip().casefold()] = d["din"]

        issuer = next((r.data.get("issuer") for r in by_section.get("general_information", []) if r.data.get("issuer")), None)
        issuer_name = (issuer or {}).get("name") or _issuer_name(self.pages) or "Issuer"
        self.issuer_id = self.entity(issuer_name, "org", cin=(issuer or {}).get("cin"))

        handlers = {
            "general_information": self.general_information, "management": self.management,
            "promoters": self.promoters, "group_companies": self.group_companies, "rpt_summary": self.rpt,
            "litigation": self.litigation, "objects": self.objects, "financial_summary": self.financials,
        }
        for key, handler in handlers.items():
            for r in by_section.get(key, []):
                handler(r)

    def general_information(self, r: Result) -> None:
        for d in r.data.get("directors") or []:
            if isinstance(d, dict) and (pid := self.entity(d.get("name"), "person", din=d.get("din"))):
                self.fact(r, d, "director", pid, self.issuer_id, designation=d.get("designation"))
        for m in r.data.get("intermediaries") or []:
            if isinstance(m, dict) and (oid := self.entity(m.get("name"), "org", reg=m.get("sebi_registration") or m.get("firm_registration"))):
                self.fact(r, m, "intermediary", oid, self.issuer_id, role=m.get("role"),
                          registration=m.get("sebi_registration") or m.get("firm_registration"))
        for c in r.data.get("auditor_changes") or []:
            if isinstance(c, dict) and (oid := self.entity(c.get("auditor"), "org")):
                self.fact(r, c, "auditor_change", oid, self.issuer_id, date=c.get("date"), reason=c.get("reason"))

    def management(self, r: Result) -> None:
        for d in r.data.get("directors") or []:
            if not isinstance(d, dict) or not (pid := self.entity(d.get("name"), "person", din=d.get("din"))):
                continue
            self.fact(r, d, "director", pid, self.issuer_id, designation=d.get("designation"))
            for company in d.get("other_directorships") or []:
                if isinstance(company, str) and (cid := self.entity(company, "org")) and cid != self.issuer_id:
                    self.fact(r, d, "directorship", pid, cid)

    def promoters(self, r: Result) -> None:
        for p in r.data.get("promoters") or []:
            if not isinstance(p, dict):
                continue
            kind = "org" if p.get("type") == "corporate" else "person"
            if pid := self.entity(p.get("name"), kind, din=p.get("din")):
                self.fact(r, p, "promoter", pid, self.issuer_id, shareholding_pct=to_number(p.get("shareholding_pct")))
        combined = r.data.get("combined_shareholding_pct")
        if isinstance(combined, dict) and to_number(combined.get("value")) is not None:
            self.fact(r, combined, "promoter_holding", None, self.issuer_id, pct=to_number(combined.get("value")))
        for e in r.data.get("promoter_group_entities") or []:
            if isinstance(e, dict) and (oid := self.entity(e.get("name"), "org")) and oid != self.issuer_id:
                self.fact(r, e, "promoter_group", oid, self.issuer_id)

    def group_companies(self, r: Result) -> None:
        for g in r.data.get("group_companies") or []:
            if isinstance(g, dict) and (oid := self.entity(g.get("name"), "org", cin=g.get("cin"))) and oid != self.issuer_id:
                self.fact(r, g, "group_company", oid, self.issuer_id)

    def rpt(self, r: Result) -> None:
        unit, fiscal = r.data.get("unit"), r.data.get("fiscal")
        for t in r.data.get("transactions") or []:
            if not isinstance(t, dict) or not t.get("party"):
                continue
            party, nature = t["party"].strip(), t.get("nature")
            # "Opticon Pipes Private Limited (Services)" is the same company; the bracket describes the transaction.
            m = re.match(r"^(.*?)\s*\(([^)]+)\)$", party)
            if m and m.group(2).strip().upper() not in ("HUF", "LLP", "INDIA", "P", "PVT"):
                party, nature = m.group(1), f"{nature} ({m.group(2).strip()})" if nature else m.group(2).strip()
            t = {**t, "nature": nature}
            kind = "org" if looks_like_org(party) else "person"
            pid = self.entity(party, kind)
            amount = to_rupees(t.get("amount"), unit)
            if pid and pid != self.issuer_id and amount:
                self.fact(r, t, "rpt", pid, self.issuer_id, amount, nature=t.get("nature"),
                          relationship=t.get("relationship"), fiscal=fiscal, pct_of_revenue=to_number(t.get("pct_of_revenue")))

    def litigation(self, r: Result) -> None:
        for item in r.data.get("items") or []:
            if not isinstance(item, dict):
                continue
            count = int(to_number(item.get("count")) or 1)
            if count <= 0:
                continue
            self.fact(r, item, "litigation", None, self.issuer_id, to_rupees(item.get("amount"), item.get("unit")),
                      party_type=item.get("party_type"), direction=item.get("direction"),
                      category=item.get("category"), count=count, summary=item.get("summary"))

    def objects(self, r: Result) -> None:
        unit = r.data.get("unit")
        # The first page of "Objects of the Issue" carries the summary table; later pages restate it in detail.
        first = not self._objects_seen
        self._objects_seen = True
        for o in (r.data.get("objects") or []) if first else []:
            if isinstance(o, dict) and o.get("purpose"):
                self.fact(r, o, "object", None, self.issuer_id, to_rupees(o.get("amount"), unit), purpose=o.get("purpose"))
        for p in r.data.get("related_party_payments") or []:
            if isinstance(p, dict) and (pid := self.entity(p.get("party"))):
                self.fact(r, p, "proceeds_to_related", pid, self.issuer_id, to_rupees(p.get("amount"), unit), purpose=p.get("purpose"))
        statement = r.data.get("no_related_party_statement")
        if isinstance(statement, dict) and statement.get("quote"):
            self.fact(r, statement, "no_related_proceeds", None, self.issuer_id)

    def financials(self, r: Result) -> None:
        unit = r.data.get("unit")
        for m in r.data.get("metrics") or []:
            if isinstance(m, dict) and m.get("metric"):
                value = to_rupees(m.get("value"), unit)
                if value is not None:
                    self.fact(r, m, "financial", None, self.issuer_id, value, metric=m.get("metric"), fiscal=m.get("fiscal"))


class Ingestor:
    def __init__(self, store: Store, llm: LLM, cfg: Settings = default_settings):
        self.store, self.llm, self.cfg = store, llm, cfg

    def add_pdf(self, src: Path, filing_id: str | None = None) -> str:
        """Copy a PDF into the data dir and register it; returns the filing id."""
        filing_id = filing_id or slugify(src.stem)
        if (existing := self.store.filing(filing_id)) and existing["pdf_path"] != str(self.cfg.filings_dir / f"{filing_id}.pdf"):
            filing_id = f"{filing_id}-{int(time.time()) % 100000}"
        dest = self.cfg.filings_dir / f"{filing_id}.pdf"
        dest.parent.mkdir(parents=True, exist_ok=True)
        if src.resolve() != dest.resolve():
            shutil.copyfile(src, dest)
        self.store.create_filing(filing_id, str(dest))
        return filing_id

    def run(self, filing_id: str) -> None:
        filing = self.store.filing(filing_id)
        started = time.monotonic()
        progress = {"stage": "reading", "message": "Reading the PDF", "done": 0, "total": 0, "found": {}}

        def push(**changes):
            progress.update(changes)
            self.store.update_filing(filing_id, status="processing", progress=progress)

        try:
            push()
            pages = [redact(p) for p in read_pages(Path(filing["pdf_path"]))]
            self.store.clear_filing_data(filing_id)
            self.store.save_pages(filing_id, pages)

            sections = locate_sections(pages)
            if "rpt_summary" not in sections and (note := related_party_note(pages, sections)):
                sections["rpt_summary"] = note
            jobs = build_jobs(sections, pages, self.cfg.chunk_chars)
            if not jobs:
                raise ValueError("Could not find any of the standard sections. Is this an Indian IPO offer document?")
            push(stage="extracting", message=f"Found {len(sections)} sections in {len(pages)} pages",
                 total=len(jobs), sections={k: [s.first_page, s.last_page] for k, s in sections.items()})

            lock = threading.Lock()

            def on_done(result: Result):
                with lock:
                    found = progress["found"]
                    for key, value in result.data.items():
                        if isinstance(value, list):
                            found[key] = found.get(key, 0) + len(value)
                    push(done=progress["done"] + 1,
                         message=f"Read {SECTION_LABEL.get(result.job.section, result.job.section)}"
                                 f" (pages {result.job.first_page}-{result.job.last_page})")

            llm = self.llm.with_session(f"footnote-{filing_id}") if hasattr(self.llm, "with_session") else self.llm
            results = run_jobs(llm, jobs, self.cfg.extract_workers, on_done)
            failed = [r for r in results if r.error]
            if len(failed) == len(results):
                raise RuntimeError(f"The model could not read this filing ({failed[0].error}).")
            self.store.save_extractions(filing_id, [(r.job.section, r.job.first_page, r.job.last_page, r.data, r.error)
                                                    for r in results])

            push(stage="linking", message="Linking people, companies and money")
            norm = Normaliser(self.store, filing_id, pages)
            norm.run(results)
            self.store.add_facts(norm.facts)

            issuer = self.store.entity(norm.issuer_id)
            meta = {
                "pages": len(pages),
                "sections": {k: {"title": s.title, "first_page": s.first_page, "last_page": s.last_page} for k, s in sections.items()},
                "facts": len(norm.facts),
                "verified": sum(f["verified"] for f in norm.facts),
                "failed_sections": sorted({f"{r.job.section} ({r.job.first_page}-{r.job.last_page})" for r in failed}),
                "seconds": round(time.monotonic() - started, 1),
                "doc_type": _doc_type(pages),
            }
            self.store.update_filing(filing_id, status="ready", company=issuer["name"], issuer_id=norm.issuer_id,
                                     meta=meta, progress={**progress, "stage": "done", "message": "Ready"})
            log.info("%s: %d facts (%d verified) in %.0fs", filing_id, meta["facts"], meta["verified"], meta["seconds"])
        except Exception as exc:  # surface any failure on the filing instead of leaving it "processing"
            log.exception("ingest of %s failed", filing_id)
            self.store.update_filing(filing_id, status="error", progress={**progress, "stage": "error", "message": str(exc)})


def relink(store: Store, filing_id: str) -> int:
    """Rebuild a filing's facts from its saved extraction, without calling the model again."""
    pages = store.all_pages(filing_id)
    results = [Result(Job(e["section"], e["first_page"], e["last_page"], ""), e["data"], e["error"])
               for e in store.extractions(filing_id)]
    if not results:
        raise ValueError(f"{filing_id} has no saved extraction; ingest it again.")
    store.clear_facts(filing_id)
    norm = Normaliser(store, filing_id, pages)
    norm.run(results)
    store.add_facts(norm.facts)
    filing = store.filing(filing_id)
    meta = {**filing["meta"], "facts": len(norm.facts), "verified": sum(f["verified"] for f in norm.facts)}
    store.update_filing(filing_id, meta=meta, issuer_id=norm.issuer_id, company=store.entity(norm.issuer_id)["name"])
    return len(norm.facts)


def _doc_type(pages: list[str]) -> str:
    head = " ".join(pages[:3]).upper()
    for label, pattern in (("DRHP", "DRAFT RED HERRING"), ("RHP", "RED HERRING PROSPECTUS"), ("Prospectus", "PROSPECTUS")):
        if pattern in head:
            return label
    return "Offer document"


def main(argv: list[str]) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if not argv:
        print(__doc__)
        return 2
    cfg = default_settings
    store = Store(cfg.db_path)
    if argv[0] == "--relink":
        for filing_id in argv[1:] or [f["id"] for f in store.filings() if f["status"] == "ready"]:
            print(f"{filing_id}: {relink(store, filing_id)} facts")
        return 0
    ingestor = Ingestor(store, OpenAICompatibleLLM(cfg.llm_api_key, cfg.llm_base_url, cfg.llm_model), cfg)
    for path in argv:
        filing_id = ingestor.add_pdf(Path(path))
        print(f"→ {filing_id}")
        ingestor.run(filing_id)
        f = store.filing(filing_id)
        print(f"  {f['status']}: {f['progress'].get('message')}  {f['meta'].get('facts', 0)} facts")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
