"""In-memory, per-upload graph store with LRU eviction and expiry."""

from __future__ import annotations

import secrets
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field

from .graph import KnowledgeGraph
from .retrieve import GraphRetriever


@dataclass
class Entry:
    graph: KnowledgeGraph
    retriever: GraphRetriever
    expires_at: float | None  # None = never (the bundled demo)
    analysis: dict | None = field(default=None)


class GraphStore:
    def __init__(self, max_graphs: int, ttl_seconds: int, clock=time.monotonic):
        self._items: OrderedDict[str, Entry] = OrderedDict()
        self._lock = threading.Lock()
        self._max = max_graphs
        self._ttl = ttl_seconds
        self._clock = clock

    def add(self, graph: KnowledgeGraph, graph_id: str | None = None, permanent: bool = False) -> str:
        # Unguessable ids: knowing the id is what grants access to an uploaded document.
        graph_id = graph_id or secrets.token_urlsafe(16)
        entry = Entry(graph, GraphRetriever(graph), None if permanent else self._clock() + self._ttl)
        with self._lock:
            self._items[graph_id] = entry
            self._items.move_to_end(graph_id)
            self._evict()
        return graph_id

    def get(self, graph_id: str) -> Entry | None:
        with self._lock:
            entry = self._items.get(graph_id)
            if entry is None:
                return None
            if entry.expires_at is not None and entry.expires_at < self._clock():
                del self._items[graph_id]
                return None
            self._items.move_to_end(graph_id)
            return entry

    def __len__(self) -> int:
        return len(self._items)

    def _evict(self) -> None:
        now = self._clock()
        for gid in [g for g, e in self._items.items() if e.expires_at is not None and e.expires_at < now]:
            del self._items[gid]
        temporary = [g for g, e in self._items.items() if e.expires_at is not None]
        for gid in temporary[: max(0, len(temporary) - self._max)]:
            del self._items[gid]
