"""Section-specific, fixed-schema extraction from an offer document."""

from __future__ import annotations

import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Callable

from .llm import LLM, LLMError, strip_thinking
from .pdftext import MAX_PAGES, Section

log = logging.getLogger(__name__)

COMMON_RULES = """Respond with ONE JSON object and nothing else: no prose, no markdown fences.
The excerpt is from an Indian IPO offer document (DRHP/RHP/prospectus). Pages are marked [Page N].
Rules:
- Extract only what the excerpt states. Never use outside knowledge. Unknown or "[●]" values are null.
- Every item has "page": the [Page N] number it appears on, and "quote": a short VERBATIM snippet
  (under 30 words) copied from that page that supports the item. Copy table rows as they appear.
- Names exactly as written, without honorifics (Mr., Mrs., Ms., Dr., Shri, Smt.).
- Numbers as plain JSON numbers without commas or currency symbols.
- Never include PAN, Aadhaar, passport, bank account, phone, email or home address details."""

SPECS: dict[str, str] = {
    "general_information": """Return:
{"issuer": {"name": str, "cin": str|null, "page": int, "quote": str} | null,
 "directors": [{"name": str, "din": str|null, "designation": str, "page": int, "quote": str}],
 "intermediaries": [{"role": "lead_manager"|"registrar"|"statutory_auditor"|"legal_counsel"|"banker_to_issue"|"syndicate_member"|"monitoring_agency"|"market_maker"|"underwriter"|"peer_reviewed_auditor",
                     "name": str, "sebi_registration": str|null, "firm_registration": str|null, "page": int, "quote": str}],
 "auditor_changes": [{"auditor": str, "date": str, "reason": str, "page": int, "quote": str}]}
Book running lead managers (BRLM) and lead managers are "lead_manager". Bankers to the company are not intermediaries; skip them.""",
    "management": """Return:
{"directors": [{"name": str, "din": str|null, "designation": str, "other_directorships": [str], "page": int, "quote": str}]}
"other_directorships": names of OTHER companies/LLPs where this person is a director or designated partner, as listed in the excerpt.""",
    "promoters": """Return:
{"promoters": [{"name": str, "type": "individual"|"corporate", "din": str|null, "shareholding_pct": number|null, "page": int, "quote": str}],
 "combined_shareholding_pct": {"value": number, "page": int, "quote": str} | null,
 "promoter_group_entities": [{"name": str, "page": int, "quote": str}]}
"promoter_group_entities": only companies, LLPs, firms, trusts or HUFs in the promoter group. Do NOT list individual relatives.""",
    "group_companies": """Return:
{"group_companies": [{"name": str, "cin": str|null, "page": int, "quote": str}]}""",
    "rpt_summary": """Return:
{"unit": "million"|"lakh"|"crore"|"thousand"|"rupees", "fiscal": str,
 "transactions": [{"party": str, "relationship": str, "nature": str, "amount": number|null, "pct_of_revenue": number|null, "page": int, "quote": str}]}
Use ONLY the most recent full fiscal year column (put its label, e.g. "Fiscal 2026", in "fiscal").
One item per party per nature of transaction (e.g. "Sale of product", "Purchase of the product", "Loan taken", "Rent paid").
"nature" is the row-group heading the party sits under. Skip rows whose amount for that fiscal is "-" or zero.""",
    "litigation": """Return:
{"items": [{"party_type": "company"|"promoter"|"director"|"subsidiary"|"group_company"|"kmp",
            "direction": "against"|"by", "category": "criminal"|"regulatory"|"tax"|"civil"|"disciplinary"|"other",
            "count": int, "amount": number|null, "unit": "million"|"lakh"|"crore"|"rupees"|null,
            "summary": str, "page": int, "quote": str}]}
If the excerpt has a summary table of counts, use it. Otherwise one item per described proceeding with count 1.
Statements that there are NO proceedings of a type must not produce an item.""",
    "objects": """Return:
{"unit": "million"|"lakh"|"crore"|"rupees",
 "objects": [{"purpose": str, "amount": number|null, "page": int, "quote": str}],
 "related_party_payments": [{"party": str, "amount": number|null, "purpose": str, "page": int, "quote": str}],
 "no_related_party_statement": {"page": int, "quote": str} | null}
"related_party_payments": any part of the proceeds to be paid to promoters, directors, group companies or other related parties.
"no_related_party_statement": a sentence stating no proceeds will be paid to promoters/directors/group companies, if present.""",
    "financial_summary": """Return:
{"unit": "million"|"lakh"|"crore"|"thousand"|"rupees",
 "metrics": [{"metric": "revenue_from_operations"|"profit_after_tax"|"net_cash_from_operating_activities"|"total_borrowings"|"net_worth",
              "fiscal": str, "value": number|null, "page": int, "quote": str}]}
Give each metric for the two most recent full fiscal years only.""",
}

UNIT = {"million": 1e6, "lakh": 1e5, "lakhs": 1e5, "crore": 1e7, "crores": 1e7, "thousand": 1e3, "rupees": 1.0}


@dataclass(frozen=True)
class Job:
    section: str
    first_page: int
    last_page: int
    text: str


@dataclass
class Result:
    job: Job
    data: dict = field(default_factory=dict)
    error: str | None = None


def build_jobs(sections: dict[str, Section], pages: list[str], chunk_chars: int) -> list[Job]:
    jobs: list[Job] = []
    for key in SPECS:
        sec = sections.get(key)
        if not sec:
            continue
        last = min(sec.last_page, sec.first_page + MAX_PAGES.get(key, 8) - 1)
        buf: list[str] = []
        start = sec.first_page
        for number in range(sec.first_page, last + 1):
            block = f"[Page {number}]\n{pages[number - 1]}"
            if buf and sum(map(len, buf)) + len(block) > chunk_chars:
                jobs.append(Job(key, start, number - 1, "\n\n".join(buf)))
                buf, start = [], number
            buf.append(block[: chunk_chars])
        if buf:
            jobs.append(Job(key, start, last, "\n\n".join(buf)))
    return jobs


def parse_json_object(text: str) -> dict | None:
    """Find and parse the outermost JSON object in model output, repairing common damage."""
    text, _ = strip_thinking(text)
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    start, end = text.find("{"), text.rfind("}")
    if start == -1:
        return None
    candidate = text[start : end + 1] if end > start else text[start:]
    # The last "}" may belong to an inner object when the reply was cut off, so also repair the whole tail.
    for attempt in (candidate, _repair(text[start:]), _repair(candidate)):
        try:
            value = json.loads(attempt)
        except json.JSONDecodeError:
            continue
        return value if isinstance(value, dict) else None
    return None


def _repair(s: str) -> str:
    s = re.sub(r",\s*([\]}])", r"\1", s)
    s = s.replace("“", '"').replace("”", '"')
    stack, in_str, esc = [], False, False
    for ch in s:
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
        elif ch in "{[":
            stack.append("}" if ch == "{" else "]")
        elif ch in "}]" and stack:
            stack.pop()
    if in_str:
        s += '"'
    s = re.sub(r",\s*$", "", s)
    return s + "".join(reversed(stack))


def run_job(llm: LLM, job: Job, retries: int = 1) -> Result:
    system = f"{COMMON_RULES}\n\n{SPECS[job.section]}"
    last_error = "no attempt made"
    for attempt in range(retries + 1):
        try:
            reply = llm.complete(system, f"Excerpt (pages {job.first_page}-{job.last_page}):\n\n{job.text}",
                                 temperature=0.0, max_tokens=8000)
        except LLMError as exc:
            last_error = str(exc)
            continue
        data = parse_json_object(reply)
        if data is not None:
            return Result(job, data)
        last_error = "model did not return valid JSON"
    log.warning("%s pages %d-%d failed: %s", job.section, job.first_page, job.last_page, last_error)
    return Result(job, error=last_error)


def run_jobs(llm: LLM, jobs: list[Job], workers: int, on_done: Callable[[Result], None] | None = None) -> list[Result]:
    def work(job: Job) -> Result:
        result = run_job(llm, job)
        if on_done:
            on_done(result)
        return result

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        return list(pool.map(work, jobs))


def to_number(value) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        s = value.replace(",", "").replace("₹", "").strip()
        m = re.fullmatch(r"\(?(-?\d+(?:\.\d+)?)\)?", s)
        if m:
            n = float(m.group(1))
            return -n if s.startswith("(") else n
    return None


def to_rupees(value, unit: str | None) -> float | None:
    n = to_number(value)
    if n is None:
        return None
    return n * UNIT.get((unit or "rupees").lower().strip(), 1.0)
