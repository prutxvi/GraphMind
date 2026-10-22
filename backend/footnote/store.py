"""SQLite persistence: filings, page text, entities shared across filings, and cited facts."""

from __future__ import annotations

import json
import re
import sqlite3
import threading
import time
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS filings (
    id TEXT PRIMARY KEY, company TEXT, issuer_id INTEGER, pdf_path TEXT,
    status TEXT, progress TEXT, meta TEXT, created_at REAL, updated_at REAL);
CREATE TABLE IF NOT EXISTS pages (
    filing_id TEXT, number INTEGER, text TEXT, PRIMARY KEY (filing_id, number));
CREATE TABLE IF NOT EXISTS entities (
    id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT, name TEXT, din TEXT, cin TEXT, reg TEXT);
CREATE TABLE IF NOT EXISTS entity_keys (key TEXT PRIMARY KEY, entity_id INTEGER);
CREATE TABLE IF NOT EXISTS facts (
    id INTEGER PRIMARY KEY AUTOINCREMENT, filing_id TEXT, kind TEXT,
    subject_id INTEGER, object_id INTEGER, attrs TEXT, amount REAL,
    page INTEGER, quote TEXT, verified INTEGER, section TEXT);
CREATE INDEX IF NOT EXISTS facts_filing ON facts(filing_id);
CREATE INDEX IF NOT EXISTS facts_subject ON facts(subject_id);
CREATE INDEX IF NOT EXISTS facts_object ON facts(object_id);
"""

_HONORIFIC = re.compile(r"^(mr|mrs|ms|miss|dr|shri|smt|sri|kumari|late)\.?\s+", re.IGNORECASE)
_ORG_HINT = re.compile(
    r"\b(limited|ltd|llp|private|pvt|corporation|corp|company|co\.|industries|enterprises|traders|trading|associates|"
    r"huf|trust|bank|foundation|ventures|holdings|capital|securities|technologies|infra|projects|services|solutions|"
    r"partners|firm|exports|agro|pipes|machines|systems)\b",
    re.IGNORECASE,
)


def norm_person(name: str) -> str:
    s = _HONORIFIC.sub("", name.strip())
    s = re.sub(r"[^\w\s]", " ", s.casefold())
    return re.sub(r"\s+", " ", s).strip()


def norm_org(name: str) -> str:
    s = name.casefold().replace("&", " and ")
    s = re.sub(r"^(m/s\.?|the)\s+", "", s.strip())
    s = re.sub(r"\bpvt\b\.?", "private", s)
    s = re.sub(r"\bltd\b\.?", "limited", s)
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"(\s(private limited|limited|llp|private))+$", "", s)
    return s.strip()


def looks_like_org(name: str) -> bool:
    return bool(_ORG_HINT.search(name))


def clean_id(value) -> str | None:
    if not isinstance(value, str):
        return None
    s = re.sub(r"[^A-Za-z0-9]", "", value).upper()
    return s or None


class Store:
    def __init__(self, path: Path | str):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(path), check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        with self._lock:
            self._db.executescript(SCHEMA)
            self._db.commit()

    # -- filings ---------------------------------------------------------------
    def create_filing(self, filing_id: str, pdf_path: str, company: str | None = None) -> None:
        now = time.time()
        with self._lock:
            self._db.execute(
                "INSERT OR REPLACE INTO filings (id, company, pdf_path, status, progress, meta, created_at, updated_at)"
                " VALUES (?, ?, ?, 'queued', '{}', '{}', ?, ?)",
                (filing_id, company, pdf_path, now, now),
            )
            self._db.commit()

    def update_filing(self, filing_id: str, **fields) -> None:
        cols, vals = [], []
        for key, value in fields.items():
            cols.append(f"{key} = ?")
            vals.append(json.dumps(value) if key in ("progress", "meta") else value)
        cols.append("updated_at = ?")
        vals.append(time.time())
        with self._lock:
            self._db.execute(f"UPDATE filings SET {', '.join(cols)} WHERE id = ?", (*vals, filing_id))
            self._db.commit()

    def _filing(self, row) -> dict | None:
        if row is None:
            return None
        d = dict(row)
        d["progress"] = json.loads(d["progress"] or "{}")
        d["meta"] = json.loads(d["meta"] or "{}")
        return d

    def filing(self, filing_id: str) -> dict | None:
        with self._lock:
            return self._filing(self._db.execute("SELECT * FROM filings WHERE id = ?", (filing_id,)).fetchone())

    def filings(self) -> list[dict]:
        with self._lock:
            rows = self._db.execute("SELECT * FROM filings ORDER BY created_at DESC").fetchall()
        return [self._filing(r) for r in rows]

    def clear_filing_data(self, filing_id: str) -> None:
        with self._lock:
            self._db.execute("DELETE FROM facts WHERE filing_id = ?", (filing_id,))
            self._db.execute("DELETE FROM pages WHERE filing_id = ?", (filing_id,))
            self._db.execute("DELETE FROM entity_keys WHERE key LIKE ?", (f"pname:{filing_id}:%",))
            self._db.commit()

    # -- pages -----------------------------------------------------------------
    def save_pages(self, filing_id: str, pages: list[str]) -> None:
        with self._lock:
            self._db.executemany(
                "INSERT OR REPLACE INTO pages (filing_id, number, text) VALUES (?, ?, ?)",
                [(filing_id, i, t) for i, t in enumerate(pages, start=1)],
            )
            self._db.commit()

    def page(self, filing_id: str, number: int) -> str | None:
        with self._lock:
            row = self._db.execute("SELECT text FROM pages WHERE filing_id = ? AND number = ?", (filing_id, number)).fetchone()
        return row["text"] if row else None

    def pages(self, filing_id: str, numbers: list[int]) -> dict[int, str]:
        if not numbers:
            return {}
        marks = ",".join("?" * len(numbers))
        with self._lock:
            rows = self._db.execute(
                f"SELECT number, text FROM pages WHERE filing_id = ? AND number IN ({marks})", (filing_id, *numbers)
            ).fetchall()
        return {r["number"]: r["text"] for r in rows}

    # -- entities --------------------------------------------------------------
    def upsert_entity(self, filing_id: str, name: str, kind: str | None = None,
                      din=None, cin=None, reg=None) -> int:
        """Find-or-create an entity. People merge across filings only by DIN; organisations by CIN,
        SEBI/firm registration or normalised name."""
        name = re.sub(r"\s+", " ", name).strip()
        kind = kind or ("org" if looks_like_org(name) else "person")
        din, cin, reg = clean_id(din), clean_id(cin), clean_id(reg)
        if kind == "person":
            keys = [f"din:{din}"] if din else []
            keys.append(f"pname:{filing_id}:{norm_person(name)}")
        else:
            keys = [k for k in (f"cin:{cin}" if cin else None, f"reg:{reg}" if reg else None) if k]
            keys.append(f"org:{norm_org(name)}")
        with self._lock:
            entity_id = None
            for key in keys:
                row = self._db.execute("SELECT entity_id FROM entity_keys WHERE key = ?", (key,)).fetchone()
                if row:
                    entity_id = row["entity_id"]
                    break
            if entity_id is None:
                cur = self._db.execute(
                    "INSERT INTO entities (kind, name, din, cin, reg) VALUES (?, ?, ?, ?, ?)", (kind, name, din, cin, reg)
                )
                entity_id = cur.lastrowid
            else:
                self._db.execute(
                    "UPDATE entities SET din = COALESCE(din, ?), cin = COALESCE(cin, ?), reg = COALESCE(reg, ?),"
                    " name = CASE WHEN length(?) > length(name) THEN ? ELSE name END WHERE id = ?",
                    (din, cin, reg, name, name, entity_id),
                )
            self._db.executemany(
                "INSERT OR IGNORE INTO entity_keys (key, entity_id) VALUES (?, ?)", [(k, entity_id) for k in keys]
            )
            self._db.commit()
        return entity_id

    def entity(self, entity_id: int) -> dict | None:
        with self._lock:
            row = self._db.execute("SELECT * FROM entities WHERE id = ?", (entity_id,)).fetchone()
        return dict(row) if row else None

    def entities(self, ids: set[int]) -> dict[int, dict]:
        ids = {i for i in ids if i is not None}
        if not ids:
            return {}
        marks = ",".join("?" * len(ids))
        with self._lock:
            rows = self._db.execute(f"SELECT * FROM entities WHERE id IN ({marks})", tuple(ids)).fetchall()
        return {r["id"]: dict(r) for r in rows}

    # -- facts -----------------------------------------------------------------
    def add_facts(self, rows: list[dict]) -> None:
        with self._lock:
            self._db.executemany(
                "INSERT INTO facts (filing_id, kind, subject_id, object_id, attrs, amount, page, quote, verified, section)"
                " VALUES (:filing_id, :kind, :subject_id, :object_id, :attrs, :amount, :page, :quote, :verified, :section)",
                [{**r, "attrs": json.dumps(r.get("attrs") or {}), "verified": int(bool(r.get("verified")))} for r in rows],
            )
            self._db.commit()

    def _facts(self, sql: str, args: tuple) -> list[dict]:
        with self._lock:
            rows = self._db.execute(sql, args).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["attrs"] = json.loads(d["attrs"] or "{}")
            d["verified"] = bool(d["verified"])
            out.append(d)
        return out

    def facts(self, filing_id: str) -> list[dict]:
        return self._facts("SELECT * FROM facts WHERE filing_id = ? ORDER BY id", (filing_id,))

    def facts_about(self, entity_id: int) -> list[dict]:
        return self._facts("SELECT * FROM facts WHERE subject_id = ? OR object_id = ? ORDER BY filing_id, id", (entity_id, entity_id))

    def search(self, q: str, limit: int = 20) -> dict:
        like = f"%{q.strip()}%"
        with self._lock:
            filings = self._db.execute(
                "SELECT id, company FROM filings WHERE status = 'ready' AND company LIKE ? LIMIT ?", (like, limit)
            ).fetchall()
            entities = self._db.execute(
                "SELECT id, kind, name, din, cin, reg FROM entities WHERE name LIKE ? OR din = ? OR cin = ? OR reg = ? LIMIT ?",
                (like, clean_id(q), clean_id(q), clean_id(q), limit),
            ).fetchall()
        return {"filings": [dict(r) for r in filings], "entities": [dict(r) for r in entities]}
