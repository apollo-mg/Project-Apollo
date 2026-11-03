"""Two-axis memory (DESIGN.md rules 4, 5, 11).

Every memory carries importance AND trust, because importance alone lets an important, wrong memory be acted on for
days. A memory found wrong is retired and linked to its correction, never deleted: the database refuses DELETE.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

KINDS = ("fact", "preference", "intention", "correction")
PROVENANCES = ("receipt", "commit", "correction", "chat", "inferred")
STATUSES = ("active", "retired", "archived")

# How long a memory may be used before it must be re-verified (rule 4). Inferences decay fastest.
DEFAULT_CHECK_DAYS = {"receipt": 90, "commit": 90, "correction": 180, "chat": 30, "inferred": 14}

# Rank boosts (rule 4: corrections and repetitions rank highest). Confirmations are capped so a memory verified fifty
# times cannot drown everything else on importance x trust alone.
CORRECTION_BOOST = 0.5
CONFIRM_BOOST = 0.15
CONFIRM_CAP = 4

SCHEMA = """
CREATE TABLE IF NOT EXISTS memories (
    id            INTEGER PRIMARY KEY,
    text          TEXT NOT NULL,
    kind          TEXT NOT NULL,
    importance    REAL NOT NULL CHECK (importance BETWEEN 0 AND 1),
    trust         REAL NOT NULL CHECK (trust BETWEEN 0 AND 1),
    provenance    TEXT NOT NULL,
    ref           TEXT NOT NULL DEFAULT '',
    created       TEXT NOT NULL,
    last_verified TEXT,
    check_by      TEXT NOT NULL,
    confirmations INTEGER NOT NULL DEFAULT 0,
    status        TEXT NOT NULL DEFAULT 'active',
    corrected_by  INTEGER REFERENCES memories(id)
);
-- Rule 5, enforced by the database rather than by convention: archive, never delete.
CREATE TRIGGER IF NOT EXISTS memories_never_delete BEFORE DELETE ON memories
BEGIN SELECT RAISE(ABORT, 'memories are retired or archived, never deleted'); END;
"""


@dataclass(frozen=True)
class Memory:
    id: int
    text: str
    kind: str
    importance: float
    trust: float
    provenance: str
    ref: str
    created: date
    last_verified: Optional[date]
    check_by: date
    confirmations: int
    status: str
    corrected_by: Optional[int]

    @property
    def score(self) -> float:
        """importance x trust, lifted for corrections and for memories the person has confirmed again."""
        boost = 1.0
        if self.kind == "correction" or self.provenance == "correction":
            boost += CORRECTION_BOOST
        boost += CONFIRM_BOOST * min(self.confirmations, CONFIRM_CAP)
        return self.importance * self.trust * boost


def _d(s: Optional[str]) -> Optional[date]:
    return date.fromisoformat(s) if s else None


class MemoryStore:
    def __init__(self, path: str = ":memory:"):
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)

    def add(self, text: str, kind: str, importance: float, trust: float, provenance: str, ref: str = "",
            today: Optional[date] = None, check_by: Optional[date] = None) -> int:
        if kind not in KINDS:
            raise ValueError(f"kind must be one of {KINDS}")
        if provenance not in PROVENANCES:
            raise ValueError(f"provenance must be one of {PROVENANCES}")
        if not (0 <= importance <= 1 and 0 <= trust <= 1):
            raise ValueError("importance and trust are in 0..1")
        today = today or date.today()
        check_by = check_by or today + timedelta(days=DEFAULT_CHECK_DAYS[provenance])
        with self.db:
            cur = self.db.execute(
                "INSERT INTO memories (text, kind, importance, trust, provenance, ref, created, check_by)"
                " VALUES (?,?,?,?,?,?,?,?)",
                (text, kind, importance, trust, provenance, ref, today.isoformat(), check_by.isoformat()))
        return cur.lastrowid

    def get(self, mem_id: int) -> Memory:
        row = self.db.execute("SELECT * FROM memories WHERE id = ?", (mem_id,)).fetchone()
        if row is None:
            raise KeyError(mem_id)
        return Memory(**{**dict(row), "created": _d(row["created"]), "last_verified": _d(row["last_verified"]),
                         "check_by": _d(row["check_by"])})

    def _active(self) -> list[Memory]:
        ids = [r[0] for r in self.db.execute("SELECT id FROM memories WHERE status = 'active'")]
        return [self.get(i) for i in ids]

    def rank(self, limit: int = 10) -> list[Memory]:
        """The active memories worth loading tonight, best first. Rule 11: the caller loads only these, not the ledger."""
        return sorted(self._active(), key=lambda m: (-m.score, m.id))[:limit]

    def due_for_check(self, today: date) -> list[Memory]:
        """Active memories past their check-by date: re-verify before use (rule 4)."""
        return [m for m in self._active() if m.check_by <= today]

    def verify(self, mem_id: int, today: date, days: Optional[int] = None) -> Memory:
        """The memory was checked and still holds: count the confirmation and push the check-by date out."""
        m = self.get(mem_id)
        if m.status != "active":
            raise ValueError(f"memory {mem_id} is {m.status}; only active memories are verified")
        days = days if days is not None else DEFAULT_CHECK_DAYS[m.provenance]
        with self.db:
            self.db.execute("UPDATE memories SET last_verified = ?, check_by = ?, confirmations = confirmations + 1"
                            " WHERE id = ?", (today.isoformat(), (today + timedelta(days=days)).isoformat(), mem_id))
        return self.get(mem_id)

    def retire(self, mem_id: int, correction_text: str, today: Optional[date] = None, ref: str = "") -> int:
        """Rule 5: the wrong claim stays (retired, linked); the correction becomes an active memory. Returns its id.

        The correction inherits at least the old claim's importance: a mistake about something that mattered is a lesson
        that matters. It is trusted highly because the person made it.
        """
        old = self.get(mem_id)
        if old.status != "active":
            raise ValueError(f"memory {mem_id} is already {old.status}")
        new_id = self.add(correction_text, "correction", importance=max(old.importance, 0.7), trust=0.95,
                          provenance="correction", ref=ref or f"corrects #{mem_id}", today=today)
        with self.db:
            self.db.execute("UPDATE memories SET status = 'retired', corrected_by = ? WHERE id = ?", (new_id, mem_id))
        return new_id

    def archive(self, mem_id: int) -> None:
        """Out of ranking and checks, still on disk."""
        self.get(mem_id)
        with self.db:
            self.db.execute("UPDATE memories SET status = 'archived' WHERE id = ?", (mem_id,))
