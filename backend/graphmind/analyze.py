"""Graph metrics plus a short LLM-written summary of them."""

from __future__ import annotations

import json
from collections import Counter

import networkx as nx

from .graph import KnowledgeGraph
from .llm import LLM, LLMError, strip_thinking

SYSTEM_PROMPT = (
    "You are GraphMind's analyst. Given knowledge-graph statistics, write 4-6 markdown bullet points: "
    "the main themes, the most important hub concepts, isolated concepts worth a second look, and notable patterns. "
    "Only use the statistics given."
)


def metrics(kg: KnowledgeGraph) -> dict:
    g = kg.to_networkx()
    degree = nx.degree_centrality(g)
    betweenness = nx.betweenness_centrality(g, k=min(200, len(g))) if len(g) > 2 else {}
    components = list(nx.connected_components(g))
    return {
        "total_nodes": g.number_of_nodes(),
        "total_edges": g.number_of_edges(),
        "density": round(nx.density(g), 4),
        "num_clusters": len(components),
        "largest_cluster_size": max((len(c) for c in components), default=0),
        "isolated_nodes": sorted(nx.isolates(g))[:10],
        "hub_nodes": [
            {"id": n, "centrality": round(c, 3), "connections": g.degree(n)}
            for n, c in sorted(degree.items(), key=lambda x: x[1], reverse=True)[:5]
        ],
        "bridge_nodes": [
            {"id": n, "score": round(s, 3)}
            for n, s in sorted(betweenness.items(), key=lambda x: x[1], reverse=True)[:3]
            if s > 0
        ],
        "group_distribution": dict(Counter(n.group for n in kg.nodes.values()).most_common()),
    }


def analyse(llm: LLM | None, kg: KnowledgeGraph) -> dict:
    stats = metrics(kg)
    relations = [f"{e.source} --{e.relation}--> {e.target}" for e in kg.edges[:25]]
    context = json.dumps({**stats, "sample_relations": relations}, indent=1)
    if llm is None:
        stats["ai_summary"] = "AI summary unavailable: no LLM API key configured."
        return stats
    try:
        summary, _ = strip_thinking(llm.complete(SYSTEM_PROMPT, context, temperature=0.4, max_tokens=600))
        stats["ai_summary"] = summary
    except LLMError as exc:
        stats["ai_summary"] = f"AI summary unavailable: {exc}"
    return stats
