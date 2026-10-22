"""Answer questions from graph facts plus source passages, with page citations."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .graph import KnowledgeGraph
from .llm import LLM, strip_thinking
from .retrieve import GraphRetriever, tokenize

SYSTEM_PROMPT = """You are GraphMind. Answer the question using ONLY the numbered sources.
Cite every claim with its source number in square brackets, e.g. [S2] or [S1][S4].
If the sources do not contain the answer, say so plainly instead of guessing.
Be concise: at most 6 sentences or bullet points."""

MAX_FACTS = 24
PASSAGE_CHARS = 1500


@dataclass
class Source:
    id: str
    kind: str  # "fact" | "passage"
    text: str
    page: int | None
    node: str | None = None


def _passage(text: str, query: str, width: int) -> str:
    """The window of a page that best overlaps the question."""
    if len(text) <= width:
        return text
    terms = set(tokenize(query))
    step = width // 3
    best, best_score = 0, -1
    for start in range(0, len(text) - width + step, step):
        score = len(terms & set(tokenize(text[start : start + width])))
        if score > best_score:
            best, best_score = start, score
    return ("..." if best else "") + text[best : best + width].strip() + "..."


def build_sources(kg: KnowledgeGraph, retriever: GraphRetriever, question: str, node_id: str | None) -> tuple[list[Source], list[str]]:
    focus = retriever.find_nodes(question, k=3)
    if node_id and node_id in kg.nodes:
        focus = [node_id, *[n for n in focus if n != node_id]][:3]

    sources: list[Source] = []
    seen: set[tuple[str, str, str]] = set()
    for nid in focus:
        node = kg.nodes[nid]
        if node.description:
            page = node.pages[0] if node.pages else None
            sources.append(Source("", "fact", f"{node.id} ({node.type}): {node.description}", page, node.id))
        for edge in kg.neighbours(nid):
            key = (edge.source, edge.relation, edge.target)
            if key in seen:
                continue
            seen.add(key)
            ev = next((e for e in edge.evidence if e.verified), edge.evidence[0] if edge.evidence else None)
            text = f"{edge.source} --{edge.relation}--> {edge.target}"
            if ev:
                text += f' (quote: "{ev.quote}")'
            sources.append(Source("", "fact", text, ev.page if ev else None, nid))
    sources = sources[:MAX_FACTS]

    page_text = {p.number: p.text for p in kg.pages}
    for number in retriever.find_pages(question, k=2):
        sources.append(Source("", "passage", _passage(page_text[number], question, PASSAGE_CHARS), number))

    for i, s in enumerate(sources, 1):
        s.id = f"S{i}"
    return sources, focus


def answer(llm: LLM, kg: KnowledgeGraph, retriever: GraphRetriever, question: str, node_id: str | None = None) -> dict:
    sources, focus = build_sources(kg, retriever, question, node_id)
    if not sources:
        return {
            "reply": "I couldn't find anything in this document related to that question.",
            "thinking": "",
            "citations": [],
            "focused_node": None,
            "related_nodes": [],
        }

    listing = "\n".join(
        f"[{s.id}] ({'page ' + str(s.page) if s.page else 'page unknown'}) {s.text}" for s in sources
    )
    raw = llm.complete(SYSTEM_PROMPT, f"Sources:\n{listing}\n\nQuestion: {question}", temperature=0.2, max_tokens=700)
    reply, thinking = strip_thinking(raw)

    by_id = {s.id: s for s in sources}
    cited = [by_id[i] for i in dict.fromkeys(re.findall(r"\[(S\d+)\]", reply)) if i in by_id]
    return {
        "reply": reply,
        "thinking": thinking,
        "citations": [{"id": s.id, "kind": s.kind, "page": s.page, "text": s.text, "node": s.node} for s in cited],
        "focused_node": focus[0] if focus else None,
        "related_nodes": focus,
    }
