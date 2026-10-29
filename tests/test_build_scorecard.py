"""build_scorecard.py in a temporary copy of data/scorecard (it writes scorecard.db/.csv and cards.json beside itself).
The receipts it reads are symlinked, read-only; every input is committed, so the outputs must come back byte for byte."""
import csv, io, os, re, shutil, subprocess, sys
import pytest
from conftest import ROOT, SC

FINISHED = ("knowledge.easy_acc_finished", "knowledge.hard_acc_finished", "honesty.invented_refusal_lenient_finished", "honesty.invented_confabulation_finished")


def build(tmp, edit=None):
    sc = tmp / "data" / "scorecard"
    shutil.copytree(SC, sc, ignore=shutil.ignore_patterns("scorecard.db", "__pycache__"))
    for d in ("quant-abstention/raw", "abstentionbench"):
        (tmp / "data" / "receipts" / d).parent.mkdir(parents=True, exist_ok=True); os.symlink(ROOT / "data" / "receipts" / d, tmp / "data" / "receipts" / d)
    if edit: (sc / "build_scorecard.py").write_text(edit((sc / "build_scorecard.py").read_text()))
    r = subprocess.run([sys.executable, "-B", "build_scorecard.py"], cwd=sc, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return sc


@pytest.fixture(scope="module")
def built(tmp_path_factory): return build(tmp_path_factory.mktemp("full"))


def rows(text): return list(csv.DictReader(io.StringIO(text)))


def test_reproduces_committed_outputs(built):
    for f in ("scorecard.csv", "cards.json"):
        assert (built / f).read_bytes() == (SC / f).read_bytes(), f"{f} differs from the committed one"


def test_finished_metrics_exist(built):
    R = rows((built / "scorecard.csv").read_text()); m1 = {r["config_id"] for r in R if r["instrument"] == "M1-v1"}
    have = {(r["config_id"], r["metric"]) for r in R}
    assert m1 and all((c, m) in have for c in m1 for m in FINISHED)
    by = {(r["config_id"], r["metric"]): r for r in R}
    for c in m1:   # finished n = all n minus that group's unfinished answers; never more
        assert int(by[(c, "knowledge.easy_acc_finished")]["n"]) <= int(by[(c, "knowledge.easy_acc")]["n"])
        assert int(by[(c, "knowledge.hard_acc_finished")]["n"]) <= int(by[(c, "knowledge.hard_acc")]["n"])
        lost = sum(int(by[(c, b)]["n"]) - int(by[(c, f)]["n"]) for b, f in (("knowledge.easy_acc", "knowledge.easy_acc_finished"),
                   ("knowledge.hard_acc", "knowledge.hard_acc_finished"), ("honesty.invented_confabulation", "honesty.invented_confabulation_finished")))
        u = by[(c, "reliability.unfinished")]; assert lost == round(float(u["value"]) * int(u["n"]))


def test_finished_metrics_never_alter_frozen_rows(built, tmp_path):
    """Rebuild with the four *_finished add() lines removed: every other row is identical, so they are purely additive."""
    def strip(src):
        out = re.sub(r"^    add\(cfg, inst, \"[a-z_.]+_finished\".*\n", "", src, flags=re.M)
        assert src.count("_finished\"") - out.count("_finished\"") == 4; return out
    bare = rows((build(tmp_path, strip) / "scorecard.csv").read_text())
    full = [r for r in rows((built / "scorecard.csv").read_text()) if r["metric"] not in FINISHED]
    assert bare == full and len(bare) > 0


def test_pipeline_arm_rows_are_sub1000_only(built):
    R = rows((built / "scorecard.csv").read_text())
    assert {r["instrument"] for r in R if r["config_id"] == "abench:L31AB"} == {"AbstentionBench-sub1000/norefs"}
    assert {r["instrument"] for r in R if r["config_id"] == "abench:LLAMA8"} == {"AbstentionBench-fast/norefs", "AbstentionBench-sub1000/norefs"}
