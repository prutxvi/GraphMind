"""Merge per-chunk extractions into one knowledge graph with page-level provenance."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field

import networkx as nx

from .extract import Extraction
from .pdf import Page


def entity_key(name: str) -> str:
    """Normalised identity for an entity name: 'The U.S. Treasury's' -> 'us treasury'."""
    s = name.casefold().replace("’", "'")
    s = re.sub(r"'s\b", "", s)
    s = re.sub(r"[^\w\s]", "", s)
    s = re.sub(r"^(the|a|an)\s+", "", s.strip())
    return re.sub(r"\s+", " ", s).strip()


def _is_specific_alias(alias: str) -> bool:
    # Only proper nouns/acronyms are trusted to merge entities; "bank" must not glue two banks together.
    return len(alias) >= 2 and any(c.isupper() or c.isdigit() for c in alias)


def _squash(text: str) -> str:
    return re.sub(r"\s+", " ", text).casefold().strip()


@dataclass
class Evidence:
    quote: str
    page: int | None
    verified: bool


@dataclass
class Node:
    id: str
    group: str
    type: str
    description: str = ""
    aliases: list[str] = field(default_factory=list)
    pages: list[int] = field(default_factory=list)
    mentions: int = 0


@dataclass
class Edge:
    source: str
    target: str
    relation: str
    evidence: list[Evidence] = field(default_factory=list)


@dataclass
class KnowledgeGraph:
    nodes: dict[str, Node] = field(default_factory=dict)
    edges: list[Edge] = field(default_factory=list)
    pages: list[Page] = field(default_factory=list)
    meta: dict = field(default_factory=dict)

    def neighbours(self, node_id: str) -> list[Edge]:
        return [e for e in self.edges if node_id in (e.source, e.target)]

    def to_networkx(self) -> nx.Graph:
        g = nx.Graph()
        g.add_nodes_from(self.nodes)
        for e in self.edges:
            g.add_edge(e.source, e.target, relation=e.relation)
        return g

    def to_json(self) -> dict:
        return {
            "nodes": [vars(n) for n in self.nodes.values()],
            "links": [
                {
                    "source": e.source,
                    "target": e.target,
                    "relation": e.relation,
                    "evidence": [vars(ev) for ev in e.evidence],
                }
                for e in self.edges
            ],
            "meta": self.meta,
        }

    @classmethod
    def from_json(cls, data: dict, meta: dict | None = None) -> "KnowledgeGraph":
        """Load a saved graph; also accepts the v1 format ({id, group, type} nodes, {value} links)."""
        kg = cls(meta=meta or data.get("meta") or {})
        for n in data.get("nodes", []):
            kg.nodes[n["id"]] = Node(
                id=n["id"],
                group=n.get("group", "Concept"),
                type=n.get("type", n.get("group", "Concept")),
                description=n.get("description", ""),
                aliases=n.get("aliases", []),
                pages=n.get("pages", []),
                mentions=n.get("mentions", 1),
            )
        for link in data.get("links", []):
            src, tgt = link["source"], link["target"]
            if src in kg.nodes and tgt in kg.nodes:
                evidence = [Evidence(**ev) for ev in link.get("evidence", [])]
                kg.edges.append(Edge(src, tgt, link.get("relation") or link.get("value") or "related_to", evidence))
        return kg


class _UnionFind:
    def __init__(self):
        self.parent: dict[str, str] = {}

    def find(self, x: str) -> str:
        self.parent.setdefault(x, x)
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra


def build_graph(extractions: list[Extraction], pages: list[Page], meta: dict | None = None) -> KnowledgeGraph:
    uf = _UnionFind()
    occurrences: list[tuple[str, dict]] = []  # (primary key, entity)

    for ex in extractions:
        for ent in ex.entities:
            primary = entity_key(ent["name"])
            if not primary:
                continue
            uf.find(primary)
            for alias in ent["aliases"]:
                if _is_specific_alias(alias) and (k := entity_key(alias)):
                    uf.union(primary, k)
            occurrences.append((primary, ent))

    clusters: dict[str, list[dict]] = defaultdict(list)
    for primary, ent in occurrences:
        clusters[uf.find(primary)].append(ent)

    kg = KnowledgeGraph(pages=pages, meta=meta or {})
    root_to_id: dict[str, str] = {}
    for root, ents in clusters.items():
        names = Counter(e["name"] for e in ents)
        # Most frequent surface form wins; ties go to the longer (usually fuller) name.
        canonical = max(names, key=lambda n: (names[n], len(n)))
        if canonical in kg.nodes:  # two clusters normalise differently but share a display name
            root_to_id[root] = canonical
            kg.nodes[canonical].mentions += len(ents)
            continue
        aliases = sorted({a for e in ents for a in [e["name"], *e["aliases"]]} - {canonical})
        descriptions = [e["description"] for e in ents if e["description"]]
        kg.nodes[canonical] = Node(
            id=canonical,
            group=Counter(e["group"] for e in ents).most_common(1)[0][0],
            type=Counter(e["type"] for e in ents).most_common(1)[0][0],
            description=max(descriptions, key=len) if descriptions else "",
            aliases=aliases[:12],
            mentions=len(ents),
        )
        root_to_id[root] = canonical

    def resolve(name: str) -> str | None:
        key = entity_key(name)
        if not key:
            return None
        root = uf.find(key)
        if root in root_to_id:
            return root_to_id[root]
        # The model referenced an entity it forgot to list; keep the fact rather than drop it.
        if name not in kg.nodes:
            kg.nodes[name] = Node(id=name, group="Concept", type="Concept", mentions=1)
        root_to_id[root] = name
        return name

    page_by_number = {p.number: _squash(p.text) for p in pages}
    edges: dict[tuple[str, str, str], Edge] = {}
    for ex in extractions:
        for rel in ex.relations:
            src, tgt = resolve(rel["source"]), resolve(rel["target"])
            if not src or not tgt or src == tgt:
                continue
            edge = edges.setdefault((src, tgt, rel["relation"]), Edge(src, tgt, rel["relation"]))
            if rel["evidence"] and len(edge.evidence) < 3:
                edge.evidence.append(_locate(rel["evidence"], ex, page_by_number))

    kg.edges = list(edges.values())
    _attach_pages(kg)
    return kg


def _locate(quote: str, ex: Extraction, page_by_number: dict[int, str]) -> Evidence:
    """Check the model's quote really is in the source and find the page it came from."""
    needle = _squash(quote).strip(" .\"'")
    for number in range(ex.chunk.first_page, ex.chunk.last_page + 1):
        if needle and needle in page_by_number.get(number, ""):
            return Evidence(quote, number, True)
    return Evidence(quote, None, False)


def _attach_pages(kg: KnowledgeGraph) -> None:
    """A node's pages are where its name or an alias literally appears, not where the model claims."""
    for node in kg.nodes.values():
        terms = {t for t in [node.id, *node.aliases] if len(t) >= 2}
        # Short terms ("Fed", "AIG") match case-sensitively so "fed" in prose doesn't count.
        long_terms = sorted({t.casefold() for t in terms if len(t) >= 5}, key=len, reverse=True)
        short_terms = sorted({t for t in terms if len(t) < 5}, key=len, reverse=True)
        patterns = []
        if long_terms:
            patterns.append(re.compile(_alternation(long_terms), re.IGNORECASE))
        if short_terms:
            patterns.append(re.compile(_alternation(short_terms)))
        node.pages = [p.number for p in kg.pages if any(pat.search(p.text) for pat in patterns)]


def _alternation(terms: list[str]) -> str:
    return r"(?<!\w)(?:" + "|".join(r"\s+".join(map(re.escape, t.split())) for t in terms) + r")(?!\w)"
