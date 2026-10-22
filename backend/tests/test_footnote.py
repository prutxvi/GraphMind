import json
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from footnote.config import Settings
from footnote.extract import parse_json_object, to_rupees
from footnote.ingest import Ingestor, redact, verify
from footnote.pdftext import locate_sections, parse_toc, page_offset, read_pages
from footnote.report import FilingReport, entity_report
from footnote.store import Store, norm_org
from main import create_app

from conftest import FakeLLM, filing_pages, make_pdf, responses


@pytest.fixture
def cfg(tmp_path):
    return replace(Settings(), data_dir=tmp_path / "data", llm_api_key=None, extract_workers=2)


@pytest.fixture
def store(cfg):
    return Store(cfg.db_path)


def ingest(store, cfg, tmp_path, company, **kw):
    path = tmp_path / f"{company.lower().replace(' ', '-')}-rhp.pdf"
    path.write_bytes(make_pdf(filing_pages(company, **kw)))
    ing = Ingestor(store, FakeLLM(responses(company, **kw)), cfg)
    fid = ing.add_pdf(path)
    ing.run(fid)
    return store.filing(fid)


# -- reading the document -----------------------------------------------------

def test_sections_found_from_contents_and_printed_page_offset(acme_pdf):
    pages = read_pages(acme_pdf)
    assert len(parse_toc(pages)) >= 10
    assert page_offset(pages) == 2
    sections = locate_sections(pages)
    assert (sections["rpt_summary"].first_page, sections["rpt_summary"].last_page) == (6, 6)
    assert sections["general_information"].first_page == 7
    assert sections["litigation"].first_page == 13
    assert {"management", "promoters", "group_companies", "objects", "financial_summary"} <= set(sections)


def test_amount_units_and_brackets():
    assert to_rupees("1,150.00", "million") == 1.15e9
    assert to_rupees("(120.50)", "million") == pytest.approx(-1.205e8)
    assert to_rupees(3, "crore") == 3e7
    assert to_rupees("[●]", "million") is None


def test_quote_verification_ignores_table_spacing():
    pages = ["x", "River Pipes Private\nLimited Entity under  common control 240.00 10.00"]
    assert verify("River Pipes Private Limited Entity under common control 240.00", 1, pages, 1, 2) == (2, True)
    assert verify("an invented sentence that is not there", 2, pages, 1, 2) == (2, False)


def test_redacts_pan_and_aadhaar():
    assert "AAJPS3762N" not in redact("PAN is AAJPS3762N.")
    assert "1234 5678 9012" not in redact("Aadhaar 1234 5678 9012")
    assert redact("CIN U45201DL2003PLC120995") == "CIN U45201DL2003PLC120995"


def test_parse_json_repairs_truncated_output():
    assert parse_json_object('```json\n{"a": [1, 2,]}\n```') == {"a": [1, 2]}
    assert parse_json_object('{"x": [{"n": "A"}, {"n": "B') == {"x": [{"n": "A"}, {"n": "B"}]}


def test_org_names_normalise():
    assert norm_org("Hill Machines Pvt. Ltd.") == norm_org("Hill Machines Private Limited") == "hill machines"


# -- one filing ---------------------------------------------------------------

def test_ingest_builds_cited_facts(store, cfg, tmp_path):
    f = ingest(store, cfg, tmp_path, "Acme Agro")
    assert f["status"] == "ready", f["progress"]
    assert f["company"] == "Acme Agro Limited"
    assert f["meta"]["facts"] > 10
    assert f["meta"]["verified"] / f["meta"]["facts"] > 0.8
    facts = store.facts(f["id"])
    assert all("AAJPS3762N" not in (x["quote"] or "") for x in facts)
    assert "AAJPS3762N" not in store.page(f["id"], 10)


def test_people_resolve_by_din_within_filing(store, cfg, tmp_path):
    f = ingest(store, cfg, tmp_path, "Acme Agro")
    facts = store.facts(f["id"])
    asha = {x["subject_id"] for x in facts if x["kind"] in ("director", "promoter", "directorship")}
    salary = {x["subject_id"] for x in facts if x["kind"] == "rpt" and x["attrs"]["nature"] == "Salary"}
    assert len(asha) == 1 and salary == asha
    assert store.entity(asha.pop())["din"] == "01174144"


def test_flags_are_rule_based_and_cited(store, cfg, tmp_path):
    f = ingest(store, cfg, tmp_path, "Acme Agro")
    flags = {fl["id"]: fl for fl in FilingReport(store, f, cfg).flags()}
    rb = flags["related_business"]
    assert rb["severity"] == "high" and rb["value"] == "15% of revenue"  # 10% sales + 5% purchases, salary excluded
    assert all(c["page"] == 6 for c in rb["citations"])
    assert flags["auditor_resigned"]["severity"] == "medium"
    assert flags["litigation"]["severity"] == "high"
    assert flags["cash_vs_profit"]["severity"] == "medium"
    assert flags["no_proceeds_to_related"]["severity"] == "ok"


def test_headline_comes_from_top_flag(store, cfg, tmp_path):
    f = ingest(store, cfg, tmp_path, "Acme Agro")
    s = FilingReport(store, f, cfg).summary()
    assert s["headline"].startswith("Acme Agro did ₹36.00 Cr of business with its own related companies")


def test_graph_places_people_companies_and_advisers(store, cfg, tmp_path):
    f = ingest(store, cfg, tmp_path, "Acme Agro")
    g = FilingReport(store, f, cfg).graph()
    cols = {n["name"]: n["column"] for n in g["nodes"]}
    assert cols["Asha Rao"] == "left"
    assert cols["River Pipes Private Limited"] == "right"
    assert cols["Northgate Capital Markets Limited"] == "top"
    money_edges = [e for e in g["edges"] if e["kind"] == "money"]
    assert {e["label"] for e in money_edges} >= {"₹24.00 Cr", "₹12.00 Cr"}


def test_failed_reading_is_reported(store, cfg, tmp_path):
    path = tmp_path / "bad.pdf"
    path.write_bytes(make_pdf(["hello"] * 3))
    ing = Ingestor(store, FakeLLM({}), cfg)
    fid = ing.add_pdf(path)
    ing.run(fid)
    assert store.filing(fid)["status"] == "error"


# -- across filings -----------------------------------------------------------

def test_same_banker_and_director_link_across_filings(store, cfg, tmp_path):
    a = ingest(store, cfg, tmp_path, "Acme Agro")
    b = ingest(store, cfg, tmp_path, "Bravo Foods", auditor_resigned=False)
    lm = next(x["subject_id"] for x in store.facts(a["id"]) if x["attrs"].get("role") == "lead_manager")
    rep = entity_report(store, lm)
    assert {ap["filing_id"] for ap in rep["appearances"]} == {a["id"], b["id"]}
    flags = {fl["id"]: fl for fl in FilingReport(store, b, cfg).flags()}
    assert flags[f"lead_manager_{lm}"]["value"] == "2 IPOs here"
    assert "auditor_resigned" not in flags


def test_sebi_order_on_lead_manager_raises_high_flag(store, cfg, tmp_path):
    cfg.data_dir.mkdir(parents=True, exist_ok=True)
    (cfg.data_dir / "sebi_orders.json").write_text(json.dumps([
        {"entity": "Northgate Capital Markets Ltd", "registration": "INM000000016", "date": "2026-01-01",
         "title": "Interim order", "url": "https://www.sebi.gov.in/example"}]))
    f = ingest(store, cfg, tmp_path, "Acme Agro")
    s = FilingReport(store, f, cfg).summary()
    assert s["flags"][0]["label"] == "Lead manager's record" or any(fl["label"] == "Lead manager's record" and fl["severity"] == "high" for fl in s["flags"])


# -- API ----------------------------------------------------------------------

def test_api_end_to_end(store, cfg, tmp_path, acme_pdf):
    llm = FakeLLM(responses("Acme Agro"))
    client = TestClient(create_app(cfg, llm=llm, store=store))
    assert client.get("/api/health").json()["uploads"] is True

    fid = client.post("/api/filings", files={"file": ("acme-agro-rhp.pdf", acme_pdf.read_bytes(), "application/pdf")}).json()["id"]
    for _ in range(200):
        st = client.get(f"/api/filings/{fid}/status").json()
        if st["status"] in ("ready", "error"):
            break
        __import__("time").sleep(0.02)
    assert st["status"] == "ready", st

    listing = client.get("/api/filings").json()
    assert listing[0]["id"] == fid and listing[0]["headline"]
    full = client.get(f"/api/filings/{fid}").json()
    assert full["graph"]["nodes"] and full["lists"]["money"]
    assert client.get(f"/api/filings/{fid}/pdf").headers["content-type"] == "application/pdf"
    assert "SUMMARY OF RELATED PARTY" in client.get(f"/api/filings/{fid}/pages/6").json()["text"]

    chat = client.post(f"/api/filings/{fid}/chat", json={"message": "Who is the lead manager?"}).json()
    assert [c["id"] for c in chat["citations"]] == ["S1"]  # the made-up [S99] is dropped

    hits = client.get("/api/search", params={"q": "Northgate"}).json()
    assert hits["entities"][0]["name"] == "Northgate Capital Markets Limited"
    assert client.get(f"/api/entities/{hits['entities'][0]['id']}").json()["appearances"]


def test_api_rejects_bad_uploads_and_works_read_only(store, cfg):
    client = TestClient(create_app(cfg, llm=FakeLLM({}), store=store))
    assert client.post("/api/filings", files={"file": ("a.pdf", b"nope", "application/pdf")}).status_code == 422
    ro = TestClient(create_app(cfg, llm=None, store=store))
    assert ro.post("/api/filings", files={"file": ("a.pdf", b"%PDF", "application/pdf")}).status_code == 503
    assert ro.get("/api/filings/missing").status_code == 404
