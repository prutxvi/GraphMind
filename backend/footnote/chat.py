"""Question answering over one filing: cited facts plus the most relevant pages."""

from __future__ import annotations

import re
import threading

from .llm import LLM, strip_thinking
from .report import FilingReport, money
from .retrieve import TfidfIndex, tokenize
from .store import Store

SYSTEM_PROMPT = """You are Footnote. Answer questions about one Indian IPO filing using ONLY the numbered sources.
Cite every claim with its source number in square brackets, e.g. [S2] or [S1][S4].
If the sources do not answer the question, say so plainly. Never guess, never give buy/sell advice.
State facts neutrally: a related-party transaction or a pending case is a disclosed fact, not proof of wrongdoing.
Be concise: at most 6 sentences or bullet points. Amounts in ₹ crore or lakh."""

PASSAGE_CHARS = 1600


def fact_text(f: dict, name) -> str:
    a, k = f["attrs"], f["kind"]
    subject = name(f["subject_id"]) if f["subject_id"] else ""
    if k == "rpt":
        pct = f" ({a['pct_of_revenue']}% of revenue)" if a.get("pct_of_revenue") else ""
        return f"Related-party transaction: {subject} ({a.get('relationship', 'related party')}), {a.get('nature', '')}, {money(f['amount'])} in {a.get('fiscal', 'latest fiscal')}{pct}."
    if k == "promoter":
        return f"Promoter: {subject}" + (f", holds {a['shareholding_pct']}%." if a.get("shareholding_pct") else ".")
    if k == "director":
        return f"Director: {subject}, {a.get('designation', 'director')}."
    if k == "directorship":
        return f"{subject} is also a director of {name(f['object_id'])}."
    if k in ("group_company", "promoter_group"):
        return f"{subject} is a {'group company' if k == 'group_company' else 'promoter group entity'}."
    if k == "intermediary":
        return f"{subject} is the {str(a.get('role', 'adviser')).replace('_', ' ')}" + (f" (registration {a['registration']})." if a.get("registration") else ".")
    if k == "auditor_change":
        return f"Auditor change: {subject}, {a.get('date', '')}, {a.get('reason', '')}."
    if k == "litigation":
        return f"Litigation {a.get('direction', '')} {a.get('party_type', '')}: {a.get('category', '')}, {a.get('count', 1)} case(s). {a.get('summary', '')}"
    if k == "object":
        return f"Use of IPO money: {a.get('purpose', '')}" + (f", {money(f['amount'])}." if f["amount"] else ".")
    if k == "proceeds_to_related":
        return f"IPO money to related party {subject}: {a.get('purpose', '')} {money(f['amount'])}."
    if k == "financial":
        return f"{str(a.get('metric', '')).replace('_', ' ').capitalize()} in {a.get('fiscal', '')}: {money(f['amount'])}."
    if k == "promoter_holding":
        return f"Promoters together hold {a.get('pct')}% before the issue."
    return f["quote"]


class Indexes:
    """Per-filing TF-IDF indexes, built on first question and kept in memory."""

    def __init__(self):
        self._cache: dict[str, tuple] = {}
        self._lock = threading.Lock()

    def get(self, store: Store, report: FilingReport):
        fid = report.filing["id"]
        with self._lock:
            if fid not in self._cache:
                facts = {str(f["id"]): f for f in report.facts}
                texts = {fid_: fact_text(f, report.name) for fid_, f in facts.items()}
                sections = report.filing["meta"].get("sections", {})
                numbers = sorted({n for s in sections.values() for n in range(s["first_page"], s["last_page"] + 1)})
                pages = store.pages(fid, numbers)
                self._cache[fid] = (facts, texts, TfidfIndex(texts), pages, TfidfIndex({str(k): v for k, v in pages.items()}))
            return self._cache[fid]

    def drop(self, filing_id: str) -> None:
        with self._lock:
            self._cache.pop(filing_id, None)


def _passage(text: str, query: str, width: int) -> str:
    if len(text) <= width:
        return text
    terms = set(tokenize(query))
    step = width // 3
    best, best_score = 0, -1
    for start in range(0, len(text) - width + step, step):
        score = len(terms & set(tokenize(text[start : start + width])))
        if score > best_score:
            best, best_score = start, score
    return ("…" if best else "") + text[best : best + width].strip() + "…"


def answer(llm: LLM, store: Store, report: FilingReport, indexes: Indexes, question: str) -> dict:
    facts, texts, fact_index, pages, page_index = indexes.get(store, report)
    sources = []
    for fid, _ in fact_index.search(question, 14):
        f = facts[fid]
        sources.append({"kind": "fact", "text": texts[fid], "page": f["page"], "quote": f["quote"], "verified": f["verified"]})
    for pid, _ in page_index.search(question, 3):
        sources.append({"kind": "page", "text": _passage(pages[int(pid)], question, PASSAGE_CHARS), "page": int(pid),
                        "quote": None, "verified": True})
    if not sources:
        return {"reply": "I couldn't find anything in this filing about that.", "citations": []}
    for i, s in enumerate(sources, 1):
        s["id"] = f"S{i}"

    listing = "\n".join(f"[{s['id']}] (page {s['page'] or '?'}) {s['text']}" for s in sources)
    raw = llm.complete(SYSTEM_PROMPT, f"Company: {report.filing['company']}\n\nSources:\n{listing}\n\nQuestion: {question}",
                       temperature=0.1, max_tokens=800)
    reply, _ = strip_thinking(raw)
    by_id = {s["id"]: s for s in sources}
    cited = [by_id[i] for i in dict.fromkeys(re.findall(r"\[(S\d+)\]", reply)) if i in by_id]
    return {"reply": reply, "citations": cited}
