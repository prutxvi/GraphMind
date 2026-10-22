from __future__ import annotations

import json
import re

import pytest


def make_pdf(pages: list[str]) -> bytes:
    """Build a minimal text PDF by hand so tests need no PDF-writing dependency."""
    objects = ["<< /Type /Catalog /Pages 2 0 R >>", None, "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    kids = []
    for text in pages:
        lines = [l.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)") for l in text.split("\n")]
        ops = "BT /F1 11 Tf 14 TL 50 780 Td " + " ".join(f"({l}) Tj T*" for l in lines) + " ET"
        objects.append(f"<< /Length {len(ops)} >>\nstream\n{ops}\nendstream")
        content_ref = len(objects)
        objects.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 842] /Contents {content_ref} 0 R /Resources << /Font << /F1 3 0 R >> >> >>")
        kids.append(f"{len(objects)} 0 R")
    objects[1] = f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(kids)} >>"

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, obj in enumerate(objects, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n{obj}\nendobj\n".encode("latin-1")
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    out += "".join(f"{o:010d} 00000 n \n" for o in offsets).encode()
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode()
    return bytes(out)


class FakeLLM:
    """Returns canned extraction JSON keyed on text found in the excerpt, and echoes sources for chat."""

    def __init__(self, extractions: dict[str, dict] | None = None, chat_reply: str | None = None):
        self.extractions = extractions or {}
        self.chat_reply = chat_reply
        self.calls: list[tuple[str, str]] = []

    def complete(self, system, user, *, temperature=0.2, max_tokens=1024):
        self.calls.append((system, user))
        if user.startswith("Excerpt"):
            merged = {"entities": [], "relations": []}
            for marker, payload in self.extractions.items():
                if marker in user:
                    merged["entities"] += payload.get("entities", [])
                    merged["relations"] += payload.get("relations", [])
            return "<think>reading</think>" + json.dumps(merged)
        if user.startswith("Sources:"):
            if self.chat_reply is not None:
                return self.chat_reply
            first = re.search(r"\[(S\d+)\]", user)
            return f"Answer based on the document [{first.group(1)}]." if first else "Not in sources."
        return "- summary bullet"


def ent(name, group="Organization", aliases=(), description="", type_=None):
    return {"name": name, "group": group, "type": type_ or group, "aliases": list(aliases), "description": description}


def rel(source, target, relation, evidence=""):
    return {"source": source, "target": target, "relation": relation, "evidence": evidence}


PAGES = [
    "The Federal Reserve (the Fed) sets interest rates.\nThe Fed regulates large banks such as Lehman Brothers.",
    "Lehman Brothers filed for bankruptcy in September 2008.\nThe collapse shocked global credit markets.",
    "AIG sold credit default swaps on mortgage securities.\nThe Fed later rescued AIG with an emergency loan.",
]

EXTRACTIONS = {
    "sets interest rates": {
        "entities": [
            ent("Federal Reserve", aliases=["Fed"], description="The US central bank."),
            ent("Lehman Brothers", description="An investment bank."),
        ],
        "relations": [rel("Federal Reserve", "Lehman Brothers", "regulates", "The Fed regulates large banks such as Lehman Brothers")],
    },
    "filed for bankruptcy": {
        "entities": [ent("Lehman Brothers"), ent("Bankruptcy of Lehman", group="Event")],
        "relations": [rel("Lehman Brothers", "Bankruptcy of Lehman", "underwent", "Lehman Brothers filed for bankruptcy in September 2008")],
    },
    "credit default swaps": {
        "entities": [ent("The Fed"), ent("AIG", description="An insurer that sold credit default swaps.")],
        "relations": [rel("The Fed", "AIG", "rescued", "this quote was invented by the model")],
    },
}


@pytest.fixture
def pdf_bytes():
    return make_pdf(PAGES)


@pytest.fixture
def fake_llm():
    return FakeLLM(EXTRACTIONS)
