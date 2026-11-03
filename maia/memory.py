"""Two-axis memory (DESIGN.md rules 4, 5, 11).

Every memory carries importance AND trust, because importance alone lets an important, wrong memory be acted on for
days. A memory found wrong is retired and linked to its correction, never deleted: the database refuses DELETE.

Memories can also record what they rest on (truth maintenance). `add(..., depends_on=[...])` / `link(id, on_id)` say
"id rests on on_id". Retiring a memory flags every active transitive dependent as needing review, with the reason (the
retired memory and the shortest path to the dependent). Flagging never edits or retires a dependent: the claim may hold
on other grounds. The person (or a check) re-verifies it with `clear_review`, or retires it in turn.

Propagation rule: a reason is the pair (dependent, retired root), recorded at most once and never removed (clearing
closes it). The flagged set is therefore "every active memory reachable from a retired one along dependency edges",
a function of the graph alone: it does not depend on the order of links or retirements, it walks through retired and
archived memories (the dependency is structural), and it terminates on cycles because each memory is visited once.
"""
from __future__ import annotations

import sqlite3
from collections import deque
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterable, Optional

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

# A memory flagged for review ranks at this fraction of its score until someone re-verifies it. Below 1, so a flagged
# memory never outranks an unflagged one of equal score (ties also break unflagged-first in rank()).
REVIEW_FACTOR = 0.5

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

-- mem_id rests on on_id.
CREATE TABLE IF NOT EXISTS dependencies (
    mem_id INTEGER NOT NULL REFERENCES memories(id),
    on_id  INTEGER NOT NULL REFERENCES memories(id),
    PRIMARY KEY (mem_id, on_id),
    CHECK (mem_id != on_id)
);
CREATE INDEX IF NOT EXISTS dependencies_on ON dependencies(on_id);
CREATE TRIGGER IF NOT EXISTS dependencies_never_delete BEFORE DELETE ON dependencies
BEGIN SELECT RAISE(ABORT, 'dependencies are never deleted'); END;

-- One row per (dependent, retired root): why mem_id needs review. Closed (resolved set), never deleted.
CREATE TABLE IF NOT EXISTS reviews (
    mem_id     INTEGER NOT NULL REFERENCES memories(id),
    retired_id INTEGER NOT NULL REFERENCES memories(id),
    path       TEXT NOT NULL,
    flagged    TEXT NOT NULL,
    resolved   TEXT,
    resolution TEXT,
    PRIMARY KEY (mem_id, retired_id)
);
CREATE TRIGGER IF NOT EXISTS reviews_never_delete BEFORE DELETE ON reviews
BEGIN SELECT RAISE(ABORT, 'review reasons are closed, never deleted'); END;
"""


@dataclass(frozen=True)
class ReviewReason:
    """Why a memory needs review: `retired_id` was retired, and `path` runs from it to the memory, both inclusive."""
    retired_id: int
    path: tuple[int, ...]
    flagged: date


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
    review_reasons: tuple[ReviewReason, ...] = ()  # open reasons only; empty unless flagged

    @property
    def needs_review(self) -> bool:
        return bool(self.review_reasons)

    @property
    def score(self) -> float:
        """importance x trust, lifted for corrections and for memories the person has confirmed again, and lowered by
        REVIEW_FACTOR while something it rests on has been retired and nobody has re-verified it."""
        boost = 1.0
        if self.kind == "correction" or self.provenance == "correction":
            boost += CORRECTION_BOOST
        boost += CONFIRM_BOOST * min(self.confirmations, CONFIRM_CAP)
        return self.importance * self.trust * boost * (REVIEW_FACTOR if self.needs_review else 1.0)


def _d(s: Optional[str]) -> Optional[date]:
    return date.fromisoformat(s) if s else None


class MemoryStore:
    def __init__(self, path: str = ":memory:"):
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)

    def add(self, text: str, kind: str, importance: float, trust: float, provenance: str, ref: str = "",
            today: Optional[date] = None, check_by: Optional[date] = None,
            depends_on: Iterable[int] = ()) -> int:
        """Store a memory. `depends_on`: ids of the memories it rests on (see `link`)."""
        depends_on = list(depends_on)
        for on_id in depends_on:
            self.get(on_id)  # KeyError before anything is written
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
        mem_id = cur.lastrowid
        for on_id in depends_on:
            self.link(mem_id, on_id, today=today)
        return mem_id

    def get(self, mem_id: int) -> Memory:
        row = self.db.execute("SELECT * FROM memories WHERE id = ?", (mem_id,)).fetchone()
        if row is None:
            raise KeyError(mem_id)
        reasons = tuple(
            ReviewReason(r["retired_id"], tuple(int(x) for x in r["path"].split(">")), _d(r["flagged"]))
            for r in self.db.execute("SELECT * FROM reviews WHERE mem_id = ? AND resolved IS NULL ORDER BY retired_id",
                                     (mem_id,)))
        return Memory(**{**dict(row), "created": _d(row["created"]), "last_verified": _d(row["last_verified"]),
                         "check_by": _d(row["check_by"]), "review_reasons": reasons})

    # -- dependencies -------------------------------------------------------------------------------------------------

    def link(self, mem_id: int, on_id: int, today: Optional[date] = None) -> None:
        """Record that `mem_id` rests on `on_id`. Idempotent; cycles are allowed (and harmless).

        If `on_id` already rests, directly or not, on a retired memory, `mem_id` and its dependents are flagged now,
        exactly as if the link had existed before the retirement.
        """
        if mem_id == on_id:
            raise ValueError("a memory cannot rest on itself")
        self.get(mem_id), self.get(on_id)
        with self.db:
            self.db.execute("INSERT OR IGNORE INTO dependencies (mem_id, on_id) VALUES (?, ?)", (mem_id, on_id))
            for root in self._retired_supports(on_id):
                self._propagate(root, today or date.today())

    def supports(self, mem_id: int) -> list[int]:
        """The memories `mem_id` rests on directly."""
        return [r[0] for r in self.db.execute("SELECT on_id FROM dependencies WHERE mem_id = ? ORDER BY on_id",
                                              (mem_id,))]

    def _edges(self, mem_id: int, up: bool) -> list[int]:
        q = ("SELECT on_id FROM dependencies WHERE mem_id = ? ORDER BY on_id" if up else
             "SELECT mem_id FROM dependencies WHERE on_id = ? ORDER BY mem_id")
        return [r[0] for r in self.db.execute(q, (mem_id,))]

    def _bfs(self, start: int, up: bool) -> dict[int, int]:
        """Breadth-first over dependency edges; returns {reached id: parent id}. Neighbours are visited in id order, so
        the parent (hence the recorded path) is the same however the graph was built. Each id is visited once: cycles
        terminate."""
        parent: dict[int, int] = {}
        seen, frontier = {start}, deque([start])
        while frontier:
            cur = frontier.popleft()
            for nxt in self._edges(cur, up):
                if nxt not in seen:
                    seen.add(nxt)
                    parent[nxt] = cur
                    frontier.append(nxt)
        return parent

    def dependents(self, mem_id: int, transitive: bool = True) -> list[int]:
        """Memories resting on `mem_id` (directly, or through others if `transitive`), in id order, whatever their
        status. `mem_id` itself is never included, even on a cycle."""
        self.get(mem_id)
        if not transitive:
            return self._edges(mem_id, up=False)
        return sorted(self._bfs(mem_id, up=False))

    def _retired_supports(self, mem_id: int) -> list[int]:
        """Retired memories among `mem_id` and everything it rests on, transitively."""
        ids = [mem_id, *self._bfs(mem_id, up=True)]
        return [i for i in sorted(set(ids)) if self.get(i).status == "retired"]

    def _propagate(self, root: int, today: date) -> None:
        """Flag every active transitive dependent of retired `root`. Caller holds the transaction."""
        parent = self._bfs(root, up=False)
        for mem_id in sorted(parent):
            if mem_id == root or self.get(mem_id).status != "active":
                continue
            path, cur = [mem_id], mem_id
            while cur != root:
                cur = parent[cur]
                path.append(cur)
            # OR IGNORE: one reason per (dependent, root), ever. A reason someone already cleared stays cleared.
            self.db.execute("INSERT OR IGNORE INTO reviews (mem_id, retired_id, path, flagged) VALUES (?,?,?,?)",
                            (mem_id, root, ">".join(str(i) for i in reversed(path)), today.isoformat()))

    def needs_review(self) -> list[Memory]:
        """Active memories with an open review reason, in id order."""
        ids = [r[0] for r in self.db.execute(
            "SELECT DISTINCT r.mem_id FROM reviews r JOIN memories m ON m.id = r.mem_id"
            " WHERE r.resolved IS NULL AND m.status = 'active' ORDER BY r.mem_id")]
        return [self.get(i) for i in ids]

    def clear_review(self, mem_id: int, today: date, days: Optional[int] = None) -> Memory:
        """A person or a check re-verified a flagged memory: close its reasons and count it as a confirmation."""
        m = self.get(mem_id)
        if not m.needs_review:
            raise ValueError(f"memory {mem_id} is not flagged for review")
        with self.db:
            self.db.execute("UPDATE reviews SET resolved = ?, resolution = 'verified'"
                            " WHERE mem_id = ? AND resolved IS NULL",
                            (today.isoformat(), mem_id))
        return self.verify(mem_id, today, days)

    def _active(self) -> list[Memory]:
        ids = [r[0] for r in self.db.execute("SELECT id FROM memories WHERE status = 'active'")]
        return [self.get(i) for i in ids]

    def rank(self, limit: int = 10) -> list[Memory]:
        """The active memories worth loading tonight, best first. Rule 11: the caller loads only these, not the ledger.
        Flagged memories rank at REVIEW_FACTOR of their score, and lose ties to unflagged ones."""
        return sorted(self._active(), key=lambda m: (-m.score, m.needs_review, m.id))[:limit]

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

        Everything that rests on the retired memory, transitively, is flagged for review (see the module docstring).
        A memory that was itself flagged has its open reasons closed as resolved by this retirement.
        """
        old = self.get(mem_id)
        if old.status != "active":
            raise ValueError(f"memory {mem_id} is already {old.status}")
        new_id = self.add(correction_text, "correction", importance=max(old.importance, 0.7), trust=0.95,
                          provenance="correction", ref=ref or f"corrects #{mem_id}", today=today)
        with self.db:
            self.db.execute("UPDATE memories SET status = 'retired', corrected_by = ? WHERE id = ?", (new_id, mem_id))
            self.db.execute("UPDATE reviews SET resolved = ?, resolution = 'retired'"
                            " WHERE mem_id = ? AND resolved IS NULL",
                            ((today or date.today()).isoformat(), mem_id))
            self._propagate(mem_id, today or date.today())
        return new_id

    def archive(self, mem_id: int) -> None:
        """Out of ranking and checks, still on disk."""
        self.get(mem_id)
        with self.db:
            self.db.execute("UPDATE memories SET status = 'archived' WHERE id = ?", (mem_id,))
