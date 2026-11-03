# Maia -- core library

The rules are in [DESIGN.md](DESIGN.md); each module names the rules it implements. Python stdlib only: no network, no
model calls, no daemon. Wiring to models, IRC and the nightly job (`tools/daydream_brief.py`) comes later.

| Module | Rules | What it holds |
|---|---|---|
| `memory.py` | 4, 5, 11 | SQLite memory with importance x trust, provenance, check-by dates; retire-and-link instead of delete (the DB refuses `DELETE`); dependencies (`depends_on`, `link`), and retiring a memory flags every transitive dependent for review (`needs_review`, `clear_review`) |
| `wake.py` | 2, 3 | Wake conditions (time / file / commit / event + hypothesis + timeout) and the daily interruption budget (default 1) |
| `ranker.py` | 6 | `decide()`: hold / concede / ask from evidence, not pressure; cost of being wrong sets firmness only |
| `outcomes.py` | 9 | Prediction-error log and a per-pattern Beta posterior; interrupt when the lower bound clears, explore while wide |

The pieces do not call each other: a caller checks `should_interrupt(pattern)` and then `InterruptionBudget.spend(today)`,
and logs the outcome either way.

Tests (about a second):

```bash
python -m pytest maia/tests -q
```
