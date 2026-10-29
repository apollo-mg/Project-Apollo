"""Argument derivation: recipe mode -> run_main.py argv -> the header row run_main.py would write, compared with the
expected fields and with the stored runs' headers (what `abstend.py check` does)."""
import json
import pytest
import abstend
import run_main
from conftest import MODES, QA, ROOT


def header(p, rc, mode):
    return run_main.header_fields(run_main.build_parser().parse_args(abstend.run_argv(rc, p, mode)))


@pytest.mark.parametrize("p, mode", MODES, ids=[f"{p.stem}:{m}" for p, m in MODES])
def test_header_fields(p, mode):
    rc = json.load(open(p)); m = rc["modes"][mode]; h = header(p, rc, mode)
    want = {"arm": m["arm"], "corpus": "M1", "max_tokens": m["max_tokens"], "thinking": m["thinking"], "template_kwargs": m.get("template_kwargs") or {},
            "skip_slot": False, "usage": True, "timeout": float(m["timeout"]), "neutral_penalties": True, "meta": abstend.meta(rc, p)}
    if m.get("system"): want["system"] = m["system"]
    if m.get("sampling"): want.update(sampling=m["sampling"], seed_base=20261025)
    assert h == want
    assert h["meta"]["recipe"] == f"data/scorecard/recipes/{p.name} sha256:{abstend.sha(p)[:12]}"
    assert rc["file"]["sha256"][:8] in h["meta"]["model"] and rc["engine"]["flags"] in h["meta"]["placement"]
    av = abstend.run_argv(rc, p, mode)
    assert av[av.index("--url") + 1] == abstend.HOSTS[rc["host"]]["url"]
    assert ("--no-think-check" in av) == bool(m.get("no_think_check"))


@pytest.mark.parametrize("p, mode", MODES, ids=[f"{p.stem}:{m}" for p, m in MODES])
def test_header_matches_stored_run(p, mode):
    rc = json.load(open(p)); arm = rc["modes"][mode]["arm"]
    got = abstend.flat(json.loads(open(QA / "raw" / f"main_{arm}.jsonl").readline())); want = abstend.flat(header(p, rc, mode))
    new = set(want) - set(got)
    assert new <= abstend.KNOWN_NEW
    assert {k: want[k] for k in set(want) - new} == {k: got.get(k, "<absent>") for k in set(want) - new}
    assert set(got) <= set(want)   # nothing stored that the recipe cannot reproduce (runtime fields are dropped by flat)
    if rc["model_id"] == "nanbeige4.3-33b": assert new == {"neutral_penalties", "meta.recipe"}   # hand-run arms, before the pipeline
    else: assert not new


def test_check_exits_zero(capsys):
    with pytest.raises(SystemExit) as e: abstend.check(None)
    assert e.value.code == 0 and "MISMATCH" not in capsys.readouterr().out


def edited(tmp_path, monkeypatch, edit):
    """An edited phi-4-mini recipe under a tmp ROOT (meta.recipe needs a path under ROOT); QA, the stored runs, stays real."""
    p = tmp_path / "data/scorecard/recipes/phi-4-mini.json"; p.parent.mkdir(parents=True)
    rc = json.load(open(ROOT / "data/scorecard/recipes/phi-4-mini.json")); edit(rc["modes"]["greedy"]); p.write_text(json.dumps(rc))
    monkeypatch.setattr(abstend, "ROOT", tmp_path); return p


def test_check_reports_a_mismatch(tmp_path, monkeypatch, capsys):
    p = edited(tmp_path, monkeypatch, lambda m: m.update(max_tokens=2048))
    with pytest.raises(SystemExit) as e: abstend.check([p])
    out = capsys.readouterr().out
    assert e.value.code == 1 and "MISMATCH PHI4MG max_tokens: recipe 2048 != stored 1024" in out


def test_check_skips_a_mode_with_no_stored_run(tmp_path, monkeypatch, capsys):
    p = edited(tmp_path, monkeypatch, lambda m: m.update(arm="NOSUCHARM"))
    with pytest.raises(SystemExit) as e: abstend.check([p])
    assert e.value.code == 0 and "no stored run, nothing to compare" in capsys.readouterr().out
