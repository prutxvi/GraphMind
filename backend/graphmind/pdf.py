"""PDF -> pages -> page-aware chunks."""

from __future__ import annotations

import io
import re
from dataclasses import dataclass

from pypdf import PdfReader
from pypdf.errors import PdfReadError


class PDFError(ValueError):
    pass


@dataclass(frozen=True)
class Page:
    number: int  # 1-based, as a reader would cite it
    text: str


@dataclass(frozen=True)
class Chunk:
    index: int
    text: str
    first_page: int
    last_page: int


def _clean(text: str) -> str:
    text = text.replace("\x00", "")
    text = re.sub(r"-\n(?=[a-z])", "", text)  # re-join hyphenated line breaks
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def read_pages(data: bytes, max_pages: int) -> tuple[list[Page], int]:
    """Return (pages with text, total page count). Empty pages are dropped."""
    if not data.startswith(b"%PDF"):
        raise PDFError("File is not a PDF.")
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise PDFError("Encrypted PDFs are not supported.")
        total = len(reader.pages)
        pages = []
        for i, page in enumerate(reader.pages[:max_pages]):
            text = _clean(page.extract_text() or "")
            if text:
                pages.append(Page(number=i + 1, text=text))
    except PdfReadError as exc:
        raise PDFError(f"Could not read PDF: {exc}") from exc
    if not pages:
        raise PDFError("No extractable text found. Scanned/image-only PDFs need OCR first.")
    return pages, total


def chunk_pages(pages: list[Page], chunk_chars: int) -> list[Chunk]:
    """Pack whole pages into chunks of roughly chunk_chars; split pages that are larger on paragraph boundaries."""
    pieces: list[tuple[int, str]] = []
    for page in pages:
        if len(page.text) <= chunk_chars:
            pieces.append((page.number, page.text))
            continue
        buf = ""
        for para in re.split(r"\n\s*\n", page.text):
            while len(para) > chunk_chars:  # a single giant paragraph
                if buf:
                    pieces.append((page.number, buf))
                    buf = ""
                pieces.append((page.number, para[:chunk_chars]))
                para = para[chunk_chars:]
            if buf and len(buf) + len(para) + 2 > chunk_chars:
                pieces.append((page.number, buf))
                buf = ""
            buf = f"{buf}\n\n{para}" if buf else para
        if buf:
            pieces.append((page.number, buf))

    chunks: list[Chunk] = []
    texts: list[str] = []
    first = last = None
    for number, text in pieces:
        if texts and sum(map(len, texts)) + len(text) > chunk_chars:
            chunks.append(Chunk(len(chunks), "\n\n".join(texts), first, last))
            texts, first = [], None
        if first is None:
            first = number
        last = number
        texts.append(f"[Page {number}]\n{text}")
    if texts:
        chunks.append(Chunk(len(chunks), "\n\n".join(texts), first, last))
    return chunks
