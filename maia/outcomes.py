"""Learn the interruption thresholds, with error bars (DESIGN.md rule 9).

Every interruption, and every interruption she held back, is logged with what she expected the person to do and what
they did. Per pattern, the "was it useful" outcomes feed a Beta posterior. She interrupts only when the interval's lower
bound clears the threshold -- the conservative start comes from that, not from a pessimistic prior -- and while the
interval is still wide she explores with a small probability, or she would never learn that a pattern is useful.
"""
from __future__ import annotations

import math
import random
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

SCHEMA = """
CREATE TABLE IF NOT EXISTS outcomes (
    id          INTEGER PRIMARY KEY,
    ts          TEXT NOT NULL,
    pattern     TEXT NOT NULL,
    interrupted INTEGER NOT NULL,  -- 0: held back
    expected    TEXT NOT NULL,
    observed    TEXT NOT NULL,
    useful      INTEGER            -- NULL until known; a held-back one is useful if the person wished she had spoken
);
"""


# --- Beta quantiles, stdlib only (regularised incomplete beta by Lentz's continued fraction, then bisection) ---

def _betacf(a: float, b: float, x: float) -> float:
    tiny, qab, qap, qam = 1e-300, a + b, a + 1, a - 1
    c, d = 1.0, 1 - qab * x / qap
    d = 1 / (d if abs(d) > tiny else tiny)
    h = d
    for m in range(1, 300):
        m2 = 2 * m
        for aa in (m * (b - m) * x / ((qam + m2) * (a + m2)), -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))):
            d = 1 + aa * d
            d = 1 / (d if abs(d) > tiny else tiny)
            c = 1 + aa / c
            c = c if abs(c) > tiny else tiny
            h *= d * c
        if abs(d * c - 1) < 1e-12:
            break
    return h


def beta_cdf(x: float, a: float, b: float) -> float:
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    front = math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log1p(-x))
    if x < (a + 1) / (a + b + 2):
        return front * _betacf(a, b, x) / a
    return 1 - front * _betacf(b, a, 1 - x) / b


def beta_ppf(q: float, a: float, b: float) -> float:
    lo, hi = 0.0, 1.0
    for _ in range(60):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if beta_cdf(mid, a, b) < q else (lo, mid)
    return (lo + hi) / 2


@dataclass(frozen=True)
class Decision:
    interrupt: bool
    reason: str  # "confident" | "explore" | "hold"
    mean: float
    low: float
    high: float
    n: int


class OutcomeLog:
    def __init__(self, path: str = ":memory:", threshold: float = 0.6, level: float = 0.9, explore: float = 0.05,
                 wide: float = 0.3, prior: tuple[float, float] = (1.0, 1.0), seed: Optional[int] = None):
        """threshold: lower bound needed to interrupt. level: credible interval mass. explore: probability of an
        exploratory interruption while the interval is wider than `wide`."""
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)
        self.threshold, self.level, self.explore, self.wide, self.prior = threshold, level, explore, wide, prior
        self.rng = random.Random(seed)

    def log(self, pattern: str, interrupted: bool, expected: str, observed: str, useful: Optional[bool] = None,
            ts: Optional[datetime] = None) -> int:
        with self.db:
            cur = self.db.execute(
                "INSERT INTO outcomes (ts, pattern, interrupted, expected, observed, useful) VALUES (?,?,?,?,?,?)",
                ((ts or datetime.now()).isoformat(timespec="seconds"), pattern, int(interrupted), expected, observed,
                 None if useful is None else int(useful)))
        return cur.lastrowid

    def surprises(self, pattern: Optional[str] = None) -> list[sqlite3.Row]:
        """The prediction errors: rows where the person did not react as she expected. These are what to learn from."""
        sql, args = "SELECT * FROM outcomes WHERE expected != observed", ()
        if pattern is not None:
            sql, args = sql + " AND pattern = ?", (pattern,)
        return self.db.execute(sql + " ORDER BY id", args).fetchall()

    def posterior(self, pattern: str) -> tuple[float, float]:
        row = self.db.execute("SELECT COALESCE(SUM(useful), 0), COUNT(useful) FROM outcomes WHERE pattern = ?",
                              (pattern,)).fetchone()
        useful, n = row
        return self.prior[0] + useful, self.prior[1] + n - useful

    def should_interrupt(self, pattern: str) -> Decision:
        a, b = self.posterior(pattern)
        tail = (1 - self.level) / 2
        low, high = beta_ppf(tail, a, b), beta_ppf(1 - tail, a, b)
        n = int(round(a + b - sum(self.prior)))
        args = dict(mean=a / (a + b), low=low, high=high, n=n)
        if low >= self.threshold:
            return Decision(True, "confident", **args)
        if high - low > self.wide and self.rng.random() < self.explore:
            return Decision(True, "explore", **args)
        return Decision(False, "hold", **args)
