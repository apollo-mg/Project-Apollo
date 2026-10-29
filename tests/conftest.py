"""Shared setup for the Abstend pipeline tests. Fast and self-contained: no GPU, no network, no /mnt path, no server or
systemd unit. The modules are imported from the repo as they are; anything that would write is pointed at tmp_path."""
import copy, json, sys
from pathlib import Path
import pytest
sys.dont_write_bytecode = True   # quant-abstention/__pycache__ holds committed .pyc files; never add to them
ROOT = Path(__file__).resolve().parents[1]
SC = ROOT / "data" / "scorecard"; QA = ROOT / "data" / "receipts" / "quant-abstention"; AB = ROOT / "data" / "receipts" / "abstentionbench"
for p in (SC, QA, AB): sys.path.insert(0, str(p))
import abstend   # noqa: E402

RECIPES = sorted((SC / "recipes").glob("*.json"))
MODES = [(p, mode) for p in RECIPES for mode in json.load(open(p))["modes"]]


def load(name):
    """A fresh, mutable copy of a committed recipe (name = model_id) and its real path."""
    p = SC / "recipes" / f"{name}.json"
    return p, copy.deepcopy(json.load(open(p)))


@pytest.fixture
def no_precheck(monkeypatch):
    """prereg calls tools/ledger_precheck.py (semantic search with --deep); the prereg text is what is under test."""
    seen = []
    monkeypatch.setattr(abstend, "precheck", lambda q: seen.append(q) or "nothing found.")
    return seen


def jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))
    return path
