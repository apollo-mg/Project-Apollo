"""compare (M1 reproduction), compare_abench (sub1000 reproduction) and verdicts (judge output -> committed csv), on
small synthetic fixtures. QA, AB and ROOT (which sub1000() reads the subset through) point at tmp."""
import csv
import pytest
import abstend
from conftest import jsonl

SUB = [("AlphaQA", "3", "1"), ("AlphaQA", "12", "0"), ("BetaQA", "7", "1")]


@pytest.fixture
def tmp_receipts(tmp_path, monkeypatch):
    qa, ab = tmp_path / "data/receipts/quant-abstention", tmp_path / "data/receipts/abstentionbench"; ab.mkdir(parents=True)
    monkeypatch.setattr(abstend, "ROOT", tmp_path); monkeypatch.setattr(abstend, "QA", qa); monkeypatch.setattr(abstend, "AB", ab)
    with open(tmp_path / abstend.INSTRUMENTS[abstend.AB_INST]["subset"], "w", newline="") as f:
        w = csv.writer(f); w.writerow(["dataset", "index", "should_abstain", "q_sha256"]); w.writerows((d, i, s, "0" * 64) for d, i, s in SUB)
    return qa, ab


def m1(qa, arm, **change):
    items = [{"id": f"M1-{g}-{i:03d}", "content": f"Exact Answer: invented {g}{i}", "finish": "stop", "grade": "CORRECT", "P_abs": 0.25 * i}
             for g in "EHU" for i in range(1, 4)]
    for k, (f, v) in change.items(): next(it for it in items if it["id"] == k)[f] = v
    jsonl(qa / "raw" / f"main_{arm}.jsonl", [{"arm": arm, "header": True}] + [it for it in items if it.get("content") != "DROP"])


@pytest.mark.parametrize("change, ok, report", [({}, True, None), ({"M1-H-002": ("content", "Exact Answer: other")}, False, "content: 1 differ (first: M1-H-002)"),
                                                ({"M1-E-001": ("finish", "length")}, False, "finish: 1 differ"), ({"M1-U-003": ("grade", "WRONG")}, False, "grade: 1 differ"),
                                                ({"M1-E-002": ("P_abs", 0.5 + 5e-7)}, True, None), ({"M1-E-002": ("P_abs", 0.5 + 2e-6)}, False, "P_abs: 1 differ"),
                                                ({"M1-E-002": ("P_abs", None)}, False, "P_abs: 1 differ"), ({"M1-H-001": ("content", "DROP")}, False, "8 shared items (9 / 8)")])
def test_compare(tmp_receipts, capsys, change, ok, report):
    qa, _ = tmp_receipts; m1(qa, "A"); m1(qa, "B", **change)
    assert abstend.compare("A", "B") is ok
    out = capsys.readouterr().out
    if report: assert report in out
    else: assert "9 shared items (9 / 9)" in out and out.count(": 0 differ") == 4


def abench(ab, arm, answer=None, verdict=None, error=None):
    subj, judge = [], []
    for d, i, s in SUB:
        k = (d, i); err = {"error": "timeout"} if error == k else {}
        subj.append({"dataset": d, "index": int(i), "content": "invented reply" if answer != k else "another reply", "finish": "stop", **err})
        judge.append({"dataset": d, "index": int(i), "should_abstain": s == "1", "verdict": (s == "1") != (verdict == k), **err})
    jsonl(ab / "raw" / f"{arm}.jsonl", subj); jsonl(ab / "raw" / f"{arm}.judge_norefs.jsonl", judge)


@pytest.mark.parametrize("change, report", [({}, "0 missing in either, 0 subject answers differ, 0 verdicts differ"),
                                            ({"answer": ("BetaQA", "7")}, "1 subject answers differ"),
                                            ({"verdict": ("AlphaQA", "12")}, "1 verdicts differ"),
                                            ({"error": ("AlphaQA", "3")}, "1 missing in either")])
def test_compare_abench(tmp_receipts, capsys, change, report):
    _, ab = tmp_receipts; abench(ab, "A"); abench(ab, "B", **change)
    assert abstend.compare_abench("A", "B") is (not change)
    assert f"on sub1000 (3 items): " in (out := capsys.readouterr().out) and report in out


def test_verdicts(tmp_receipts, capsys):
    _, ab = tmp_receipts
    jsonl(ab / "raw" / "X.judge_norefs.jsonl", [
        {"dataset": "BetaQA", "index": 7, "should_abstain": True, "verdict": None},
        {"dataset": "AlphaQA", "index": 12, "should_abstain": False, "verdict": False},
        {"dataset": "AlphaQA", "index": 3, "should_abstain": True, "verdict": True, "judge_text": "Invented judge reasoning."},
        {"dataset": "AlphaQA", "index": 3, "error": "connection reset"}])
    abstend.verdicts("X")
    assert (ab / "verdicts_X.csv").read_bytes() == b"dataset,index,should_abstain,norefs\r\nAlphaQA,3,1,1\r\nAlphaQA,12,0,0\r\nBetaQA,7,1,\r\n"   # csv.writer: CRLF, as committed
    assert "3 of 3 items judged, 1 judge errors, 1 unparsed" in capsys.readouterr().out


def test_verdicts_refuses_items_outside_sub1000(tmp_receipts):
    _, ab = tmp_receipts
    jsonl(ab / "raw" / "X.judge_norefs.jsonl", [{"dataset": "AlphaQA", "index": 4, "should_abstain": True, "verdict": True}])
    with pytest.raises(SystemExit, match="1 judged items are not in sub1000"): abstend.verdicts("X")
    assert not (ab / "verdicts_X.csv").exists()
