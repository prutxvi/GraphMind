"""Per-chunk entity/relation extraction with tolerant JSON parsing."""

from __future__ import annotations

import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from .llm import LLM, LLMError, strip_thinking
from .pdf import Chunk

log = logging.getLogger(__name__)

GROUPS = ("Person", "Organization", "Place", "Event", "Concept", "Technology", "Method", "Document", "Metric")

SYSTEM_PROMPT = f"""You extract a knowledge graph from a document excerpt.
Respond with ONE JSON object and nothing else: no prose, no markdown fences, no <think> tags.

Schema:
{{"entities": [{{"name": str, "group": one of {list(GROUPS)}, "type": str, "aliases": [str], "description": str}}],
  "relations": [{{"source": str, "target": str, "relation": str, "evidence": str}}]}}

Rules:
- Only include entities and relations the excerpt actually states. Do not use outside knowledge.
- "name": the fullest proper name used in the excerpt. Put abbreviations and short forms in "aliases".
- "type": a short specific subtype, e.g. "Central bank", "Mortgage product".
- "description": one sentence, grounded in the excerpt.
- "relation": a short snake_case verb phrase, e.g. "regulates", "caused", "part_of", "located_in".
- "source" and "target" must exactly match an entity "name".
- "evidence": a short VERBATIM quote (under 30 words) from the excerpt that supports the relation.
- Skip generic words ("the report", "this chapter"). Prefer 10-30 entities per excerpt."""


@dataclass
class Extraction:
    chunk: Chunk
    entities: list[dict] = field(default_factory=list)
    relations: list[dict] = field(default_factory=list)
    error: str | None = None


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
    s = re.sub(r",\s*([\]}])", r"\1", s)  # trailing commas
    s = s.replace("“", '"').replace("”", '"')
    # Close brackets left open by a truncated response, innermost first.
    stack = []
    in_str = esc = False
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


def _str(value) -> str:
    return re.sub(r"\s+", " ", value).strip() if isinstance(value, str) else ""


def normalise(raw: dict) -> tuple[list[dict], list[dict]]:
    """Coerce model output into the schema, dropping malformed items rather than failing the chunk."""
    entities = []
    for item in raw.get("entities") or raw.get("nodes") or []:
        if not isinstance(item, dict):
            continue
        name = _str(item.get("name") or item.get("id"))
        if not name or len(name) > 120:
            continue
        group = _str(item.get("group")).title()
        aliases = [a for a in (_str(x) for x in item.get("aliases") or [] if isinstance(x, str)) if a and a != name]
        entities.append(
            {
                "name": name,
                "group": group if group in GROUPS else "Concept",
                "type": _str(item.get("type")) or group or "Concept",
                "aliases": aliases[:8],
                "description": _str(item.get("description"))[:400],
            }
        )
    relations = []
    for item in raw.get("relations") or raw.get("links") or []:
        if not isinstance(item, dict):
            continue
        src, tgt = _str(item.get("source")), _str(item.get("target"))
        rel = _str(item.get("relation") or item.get("value")).lower().replace(" ", "_") or "related_to"
        if src and tgt and src != tgt:
            relations.append({"source": src, "target": tgt, "relation": rel[:60], "evidence": _str(item.get("evidence"))[:300]})
    return entities, relations


def extract_chunk(llm: LLM, chunk: Chunk, retries: int = 1) -> Extraction:
    last_error = "no attempt made"
    for attempt in range(retries + 1):
        try:
            reply = llm.complete(
                SYSTEM_PROMPT,
                f"Excerpt (pages {chunk.first_page}-{chunk.last_page}):\n\n{chunk.text}",
                temperature=0.1 if attempt == 0 else 0.0,
                max_tokens=4096,
            )
        except LLMError as exc:
            last_error = str(exc)
            continue
        parsed = parse_json_object(reply)
        if parsed is None:
            last_error = "model did not return valid JSON"
            continue
        entities, relations = normalise(parsed)
        if entities:
            return Extraction(chunk, entities, relations)
        last_error = "model returned no entities"
    log.warning("chunk %d (pages %d-%d) failed: %s", chunk.index, chunk.first_page, chunk.last_page, last_error)
    return Extraction(chunk, error=last_error)


def extract_all(llm: LLM, chunks: list[Chunk], workers: int) -> list[Extraction]:
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        return list(pool.map(lambda c: extract_chunk(llm, c), chunks))
