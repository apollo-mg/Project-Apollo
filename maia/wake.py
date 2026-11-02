"""Wake conditions and the interruption budget (DESIGN.md rules 2, 3).

Maia ends a turn by saying what would make the next turn worth having -- a time, a file, a commit or an event -- and
which hypothesis she is waiting to check. Nothing here wakes a model: `due()` is the cheap gate's input, a list of what
fired and why. A condition that never fires still fires at its timeout, because "it never happened" is also an answer
to the hypothesis.
"""
from __future__ import annotations

import fnmatch
import sqlite3
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Iterable, Mapping, Optional

TRIGGERS = ("time", "file", "commit", "event")

SCHEMA = """
CREATE TABLE IF NOT EXISTS wake_conditions (
    id         INTEGER PRIMARY KEY,
    trigger    TEXT NOT NULL,
    spec       TEXT NOT NULL,
    hypothesis TEXT NOT NULL,
    timeout    TEXT NOT NULL,
    status     TEXT NOT NULL DEFAULT 'pending',  -- pending | fired
    fired_at   TEXT,
    reason     TEXT                              -- matched | timeout
);
"""


@dataclass(frozen=True)
class WakeCondition:
    """trigger: time (spec = ISO datetime), file (spec = glob), commit (spec = substring of hash or message),
    event (spec = event name). timeout: when to wake anyway and report the hypothesis unmet."""
    trigger: str
    spec: str
    hypothesis: str
    timeout: datetime
    id: Optional[int] = None

    def matches(self, now: datetime, obs: Mapping[str, Iterable[str]]) -> bool:
        if self.trigger == "time":
            return now >= datetime.fromisoformat(self.spec)
        seen = obs.get(self.trigger, ())
        if self.trigger == "file":
            return any(fnmatch.fnmatch(p, self.spec) for p in seen)
        if self.trigger == "commit":
            return any(self.spec in c for c in seen)
        return self.spec in seen  # event


@dataclass(frozen=True)
class Firing:
    condition: WakeCondition
    reason: str  # "matched" or "timeout"


class WakeStore:
    def __init__(self, path: str = ":memory:"):
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)

    def add(self, cond: WakeCondition) -> int:
        if cond.trigger not in TRIGGERS:
            raise ValueError(f"trigger must be one of {TRIGGERS}")
        if not cond.hypothesis.strip():
            raise ValueError("a wake condition without a hypothesis is a timer (rule 3)")
        if cond.trigger == "time":
            datetime.fromisoformat(cond.spec)  # fail at set time, not at wake time
        with self.db:
            cur = self.db.execute("INSERT INTO wake_conditions (trigger, spec, hypothesis, timeout) VALUES (?,?,?,?)",
                                  (cond.trigger, cond.spec, cond.hypothesis, cond.timeout.isoformat()))
        return cur.lastrowid

    def pending(self) -> list[WakeCondition]:
        rows = self.db.execute("SELECT * FROM wake_conditions WHERE status = 'pending' ORDER BY id")
        return [WakeCondition(r["trigger"], r["spec"], r["hypothesis"], datetime.fromisoformat(r["timeout"]), r["id"])
                for r in rows]

    def due(self, now: datetime, observations: Optional[Mapping[str, Iterable[str]]] = None) -> list[Firing]:
        """Conditions that fired since the last call. Each fires once; it is marked so a re-poll does not re-wake."""
        obs = {k: list(v) for k, v in (observations or {}).items()}
        fired = []
        for c in self.pending():
            if c.matches(now, obs):
                fired.append(Firing(c, "matched"))
            elif now >= c.timeout:
                fired.append(Firing(c, "timeout"))
        with self.db:
            for f in fired:
                self.db.execute("UPDATE wake_conditions SET status = 'fired', fired_at = ?, reason = ? WHERE id = ?",
                                (now.isoformat(), f.reason, f.condition.id))
        return fired


@dataclass
class InterruptionBudget:
    """A few interruptions a day, starting at one (rule 2). Scarcity is the point: it forces her to pick the best one.

    In memory only for now; whatever runs the nightly job persists it if it ever needs to survive a restart.
    """
    per_day: int = 1
    _day: Optional[date] = field(default=None, repr=False)
    _spent: int = field(default=0, repr=False)

    def _roll(self, today: date) -> None:
        if today != self._day:
            self._day, self._spent = today, 0

    def remaining(self, today: date) -> int:
        self._roll(today)
        return self.per_day - self._spent

    def spend(self, today: date) -> bool:
        """Take one interruption if any is left today. False means: hold it, log it as held back."""
        if self.remaining(today) <= 0:
            return False
        self._spent += 1
        return True
