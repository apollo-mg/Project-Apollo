"""AbstentionBench subset: stratified selection, the question-hash freeze (--verify) and the committed CSVs. Item text
is invented here; AbstentionBench and GPQA questions never enter the repo."""
import csv, json, math, random, shutil, subprocess, sys
from collections import Counter
import pytest
import make_subset as M
from conftest import AB, jsonl

SIZES = {("AlphaQA", True): 300, ("AlphaQA", False): 400, ("BetaQA", True): 150, ("BetaQA", False): 50,
         ("GammaQA", True): 2, ("GammaQA", False): 250, ("DeltaQA", True): 1, ("DeltaQA", False): 47}   # 1,200 items


def synthetic():
    items, i = [], 0
    for (d, sa), k in SIZES.items():
        for _ in range(k): items.append({"dataset": d, "index": i, "should_abstain": sa, "question": f"Invented question {i} about {d}?"}); i += 1
    return items


keys = lambda s: {(it["dataset"], it["index"]) for it in s}


def test_select_deterministic_and_order_free():
    items = synthetic(); a = M.select(items, 500); random.Random(7).shuffle(items)
    assert M.select(items, 500) == a


def quota_ok(sub, n):
    cells = Counter((it["dataset"], it["should_abstain"]) for it in sub)
    assert len(sub) == len(keys(sub)) == n
    assert set(cells) == set(SIZES)   # every cell at least 1, including those whose exact quota is under 1
    for c, k in cells.items(): assert k <= max(1, math.ceil(n * SIZES[c] / 1200)) and k >= math.floor(n * SIZES[c] / 1200)


@pytest.mark.parametrize("n", [40, 100, 1200])
def test_select_quotas(n):
    quota_ok(M.select(synthetic(), n), n)


# FIXED 2026-10-29, reported by this suite: a cell raised to the 1-item floor keeps its fractional part and can also win a remainder seat. At N = 1,000
# DeltaQA/True (1 item, exact 0.83) gets quota 2 > its size, so select() returns 999 items; its assert checks the quotas,
# not the selection. At N = 500 GammaQA/True (2 items, exact 0.83) gets 2 seats. Latent: in the committed data every
# cell's exact quota is >= 1.75 (test_committed_subsets_reselect_from_text_free_labels), so the frozen subsets are unaffected.
@pytest.mark.parametrize("n", [500, 1000])
def test_select_quotas_with_floor_raised_cells(n):
    quota_ok(M.select(synthetic(), n), n)


def test_select_too_small_n_is_an_assertion():
    """Below the minimum (here 21 for n = 20: the 1-per-cell floor already overshoots) the quota assert stops it."""
    with pytest.raises(AssertionError): M.select(synthetic(), 20)


def test_select_nested():
    items = synthetic(); assert keys(M.select(items, 500)) <= keys(M.select(items, 1000))


def test_containment_is_asserted_not_assumed(tmp_path):
    """Largest remainder is not monotone in N (the Alabama paradox), with or without the floor-raised-cell fix: cells
    2, 6, 6 are not nested between N = 10 and N = 11 (the original 2, 8, 8 example at 6/7 only failed through that bug,
    fixed 2026-10-29). main() must refuse such a pair rather than write a subset_N that is not inside subset_nested."""
    items = [{"dataset": f"D{c}", "index": i, "should_abstain": True, "question": f"Invented {c}.{i}"} for c, k in enumerate((2, 6, 6)) for i in range(k)]
    assert not keys(M.select(items, 10)) <= keys(M.select(items, 11))
    r = subprocess.run([sys.executable, "-I", str(AB / "make_subset.py"), str(jsonl(tmp_path / "items.jsonl", items)), "--n", "10", "--nested", "11"],
                       capture_output=True, text=True)
    assert r.returncode == 1 and "subset_10 is not contained in subset_11" in r.stderr


@pytest.fixture
def frozen(tmp_path, monkeypatch):
    """Items and a written subset_500.csv in tmp (main --write writes next to the script: HERE is pointed at tmp)."""
    items = synthetic(); f = jsonl(tmp_path / "items.jsonl", items); monkeypatch.setattr(M, "HERE", tmp_path)
    run(monkeypatch, str(f), "--n", "500", "--nested", "1000", "--write")
    return items, tmp_path


def run(monkeypatch, *argv):
    monkeypatch.setattr(sys, "argv", ["make_subset.py", *argv]); M.main()


def test_write_format(frozen):
    items, tmp = frozen; rows = list(csv.DictReader(open(tmp / "subset_500.csv"))); q = {(it["dataset"], str(it["index"])): it for it in items}
    assert len(rows) == 500 and list(rows[0]) == ["dataset", "index", "should_abstain", "q_sha256"]
    for r in rows:
        it = q[(r["dataset"], r["index"])]
        assert r["q_sha256"] == M.qhash(it["question"]) and r["should_abstain"] == str(int(it["should_abstain"]))
    assert "Invented" not in (tmp / "subset_500.csv").read_text()   # a hash, never the text


def test_verify_and_emit(frozen, monkeypatch, capsys):
    items, tmp = frozen
    run(monkeypatch, str(tmp / "items.jsonl"), "--verify", str(tmp / "subset_500.csv"), "--emit", str(tmp / "out.jsonl"))
    assert "verified: 500 subset items" in capsys.readouterr().out
    out = [json.loads(l) for l in open(tmp / "out.jsonl")]
    want = [(r["dataset"], r["index"]) for r in csv.DictReader(open(tmp / "subset_500.csv"))]
    assert [(o["dataset"], str(o["index"])) for o in out] == want and all(o["question"].startswith("Invented") for o in out)


def _text(it): it["question"] += " "
def _label(it): it["should_abstain"] = not it["should_abstain"]


@pytest.mark.parametrize("change", [_text, _label, None], ids=["question_text", "label", "item_missing"])
def test_verify_refuses(frozen, monkeypatch, change):
    items, tmp = frozen; first = next(csv.DictReader(open(tmp / "subset_500.csv")))
    k = next(i for i, it in enumerate(items) if (it["dataset"], str(it["index"])) == (first["dataset"], first["index"]))
    if change: change(items[k])
    else: del items[k]
    f = jsonl(tmp / "changed.jsonl", items)
    with pytest.raises(SystemExit, match=r"REFUSED: 1 of 500 subset items missing or changed"):
        run(monkeypatch, str(f), "--verify", str(tmp / "subset_500.csv"), "--emit", str(tmp / "out.jsonl"))
    assert not (tmp / "out.jsonl").exists()   # nothing emitted from a refused subset


def committed(n): return {(r["dataset"], r["index"]): r for r in csv.DictReader(open(AB / f"subset_{n}.csv"))}


def test_committed_subsets_nested():
    s5, s10 = committed(500), committed(1000)
    assert len(s5) == 500 and len(s10) == 1000 and set(s5) <= set(s10)
    assert all(s5[k] == s10[k] for k in s5)   # same label and question hash in both


def test_committed_subsets_reselect_from_text_free_labels():
    """Selection reads only dataset, index and label, so the full fast subset's committed verdict table (2,004 items, no
    text) reproduces the frozen subsets exactly."""
    items = [{"dataset": r["dataset"], "index": int(r["index"]), "should_abstain": r["should_abstain"] == "1"}
             for r in csv.DictReader(open(AB / "verdicts_LLAMA8.csv"))]
    assert len(items) == 2004
    cells = Counter((it["dataset"], it["should_abstain"]) for it in items)
    assert min(500 * k / 2004 for k in cells.values()) >= 1   # the 1-per-cell floor never fired for the frozen subsets
    for n in (500, 1000):
        S = committed(n); assert {(d, str(i)) for d, i in keys(M.select(items, n))} == set(S)
        lab = {(it["dataset"], str(it["index"])): str(int(it["should_abstain"])) for it in items}
        assert all(lab[k] == r["should_abstain"] for k, r in S.items())


def test_check_subset_reproduces_committed_results(tmp_path):
    """The registered check, run on a copy (it writes RESULT_abench_subset_<N>.json beside itself), gives the committed
    results for both subsets."""
    for f in ("check_subset.py", "subset_500.csv", "subset_1000.csv", "verdicts_LLAMA8.csv", "verdicts_Q27.csv"): shutil.copy(AB / f, tmp_path)
    for n in (500, 1000):
        r = subprocess.run([sys.executable, "-B", "check_subset.py", "--n", str(n)], cwd=tmp_path, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        assert json.load(open(tmp_path / f"RESULT_abench_subset_{n}.json")) == json.load(open(AB / f"RESULT_abench_subset_{n}.json"))
