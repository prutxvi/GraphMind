"""Small TF-IDF index for retrieving facts and pages (no external embedding API needed)."""

from __future__ import annotations

import math
import re
from collections import Counter


_STOP = set(
    "a an and are as at be by did do does for from has have how i in is it its me of on or tell that the this to "
    "was were what when where which who whom why will with about can you your please explain describe".split()
)


def tokenize(text: str) -> list[str]:
    tokens = []
    for tok in re.findall(r"[a-z0-9]+", text.casefold()):
        if tok in _STOP or len(tok) < 2:
            continue
        # Light stemming: enough to match "banks"/"bank", "regulated"/"regulate".
        for suffix in ("ies", "ing", "ed", "es", "s"):
            if len(tok) > len(suffix) + 3 and tok.endswith(suffix):
                tok = tok[: -len(suffix)] + ("y" if suffix == "ies" else "")
                break
        tokens.append(tok)
    return tokens


class TfidfIndex:
    def __init__(self, docs: dict[str, str]):
        self.ids = list(docs)
        counts = {doc_id: Counter(tokenize(text)) for doc_id, text in docs.items()}
        df = Counter(tok for c in counts.values() for tok in c)
        n = max(len(docs), 1)
        self.idf = {tok: math.log((1 + n) / (1 + f)) + 1 for tok, f in df.items()}
        self.vectors = {doc_id: self._weigh(c) for doc_id, c in counts.items()}

    def _weigh(self, counts: Counter) -> dict[str, float]:
        vec = {t: (1 + math.log(c)) * self.idf.get(t, 0.0) for t, c in counts.items()}
        norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
        return {t: v / norm for t, v in vec.items()}

    def search(self, query: str, k: int) -> list[tuple[str, float]]:
        q = self._weigh(Counter(tokenize(query)))
        if not q:
            return []
        scores = [(doc_id, sum(w * vec.get(t, 0.0) for t, w in q.items())) for doc_id, vec in self.vectors.items()]
        scores = [s for s in scores if s[1] > 0]
        scores.sort(key=lambda s: s[1], reverse=True)
        return scores[:k]
