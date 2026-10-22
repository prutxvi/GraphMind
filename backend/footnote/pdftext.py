"""PDF -> per-page text, plus locating the sections of an Indian offer document."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError


class PDFError(ValueError):
    pass


@dataclass(frozen=True)
class Section:
    key: str
    title: str
    first_page: int  # 1-based PDF page index (what a viewer opens), inclusive
    last_page: int


# Sections Footnote reads, matched against the filing's own table of contents.
# Wording differs between filings ("Issue"/"Offer", "Promoter"/"Promoters"), hence the patterns.
SECTION_PATTERNS: dict[str, str] = {
    "rpt_summary": r"^summary of (the )?related party transactions",
    "financial_summary": r"^summary (of )?(restated )?financial (information|statements)|^summary financial information",
    "general_information": r"^general information",
    "objects": r"^objects? of the (issue|offer)",
    "management": r"^our management",
    "promoters": r"^our promoters?( and| &) promoter group",
    "group_companies": r"^(our )?group (companies|company|entities)",
    "restated_financials": r"^(restated )?financial (information|statements)( of (the|our) company)?$|^restated (consolidated |standalone )?financial",
    "litigation": r"^outstanding litigations?( and material developments)?",
}

# A section can run long (management bios, litigation lists); cap what we send to the model.
MAX_PAGES = {
    "rpt_summary": 6,
    "financial_summary": 6,
    "general_information": 9,
    "objects": 8,
    "management": 18,
    "promoters": 8,
    "group_companies": 6,
    "litigation": 14,
}


def clean(text: str) -> str:
    text = text.replace("\x00", "").replace(" ", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def read_pages(path: Path) -> list[str]:
    data = path.read_bytes()
    if not data.startswith(b"%PDF"):
        raise PDFError("File is not a PDF.")
    try:
        reader = PdfReader(str(path))
        if reader.is_encrypted:
            raise PDFError("Encrypted PDFs are not supported.")
        pages = [clean(p.extract_text() or "") for p in reader.pages]
    except PdfReadError as exc:
        raise PDFError(f"Could not read PDF: {exc}") from exc
    if sum(len(p) for p in pages) < 2000:
        raise PDFError("Almost no text found. Scanned/image-only PDFs need OCR first.")
    return pages


_TOC_LINE = re.compile(r"^\s*(?P<title>[A-Z][A-Z0-9 ,’'&()/:\-.]+?)\s*\.{2,}\s*(?P<page>\d{1,4})\s*$")
_TOC_LINE_NODOTS = re.compile(r"^\s*(?P<title>[A-Z][A-Z0-9 ,’'&()/:\-]{6,}?)\s{1,}(?P<page>\d{1,4})\s*$")


def parse_toc(pages: list[str]) -> list[tuple[str, int]]:
    """(title, printed page) pairs from the table of contents in the first pages."""
    for text in pages[:15]:
        if not re.search(r"table of contents|^\s*contents\s*$", text, re.IGNORECASE | re.MULTILINE):
            continue
        entries = []
        for line in text.splitlines():
            m = _TOC_LINE.match(line) or _TOC_LINE_NODOTS.match(line)
            if m:
                title = re.sub(r"\s+", " ", m.group("title")).strip(" .")
                title = re.sub(r"^SECTION [IVXL]+\s*[:\-]\s*", "", title)
                entries.append((title, int(m.group("page"))))
        if len(entries) >= 8:
            return entries
    return []


def page_offset(pages: list[str]) -> int:
    """PDF index minus printed page number, voted over pages whose first or last line is a bare number."""
    votes: Counter[int] = Counter()
    for i, text in enumerate(pages, start=1):
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        for line in (lines[:1] + lines[-1:]) if lines else []:
            if re.fullmatch(r"\d{1,4}", line) and int(line) <= i:
                votes[i - int(line)] += 1
    return votes.most_common(1)[0][0] if votes else 0


def _heading_page(pages: list[str], pattern: str, start: int = 0) -> int | None:
    """First page (0-based) whose opening lines carry the heading; a fallback when the TOC is unusable."""
    rx = re.compile(pattern, re.IGNORECASE)
    for i in range(start, len(pages)):
        head = [l.strip() for l in pages[i].splitlines()[:8] if l.strip()]
        if any(rx.search(l) for l in head) and "table of contents" not in pages[i].lower():
            return i
    return None


def locate_sections(pages: list[str]) -> dict[str, Section]:
    toc = parse_toc(pages)
    offset = page_offset(pages)
    found: dict[str, Section] = {}
    n = len(pages)

    if toc:
        ordered = sorted(toc, key=lambda e: e[1])
        for idx, (title, printed) in enumerate(ordered):
            for key, pattern in SECTION_PATTERNS.items():
                if key in found or not re.search(pattern, title, re.IGNORECASE):
                    continue
                nxt = next((p for _, p in ordered[idx + 1 :] if p > printed), printed + 1)
                first = min(max(printed + offset, 1), n)
                last = min(max(nxt - 1 + offset, first), n)
                found[key] = Section(key, title.title(), first, last)

    for key, pattern in SECTION_PATTERNS.items():
        if key in found:
            continue
        i = _heading_page(pages, pattern, start=5)
        if i is not None:
            found[key] = Section(key, pattern, i + 1, min(i + MAX_PAGES.get(key, 6), n))
    return found


def related_party_note(pages: list[str], sections: dict[str, Section]) -> Section | None:
    """The related-party note inside the restated financials, for filings without a summary table."""
    fin = sections.get("restated_financials")
    lo, hi = (fin.first_page - 1, fin.last_page) if fin else (0, len(pages))
    rx = re.compile(r"related party (transactions|disclosures)", re.IGNORECASE)
    for i in range(lo, hi):
        head = " ".join(pages[i].splitlines()[:12])
        if rx.search(head) and re.search(r"nature of (the )?relationship|name of (the )?related part", pages[i], re.IGNORECASE):
            return Section("rpt_summary", "Related party transactions (restated financials)", i + 1, min(i + 6, len(pages)))
    return None
