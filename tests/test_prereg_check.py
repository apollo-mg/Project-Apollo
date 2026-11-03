"""tools/prereg_check.py on synthetic preregs. ledger_precheck is stubbed and INDEX.md is a tmp file: no network,
no /mnt path, no git history needed."""
import datetime, subprocess, sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import prereg_check as pc   # noqa: E402

INDEX_ROWS = [
    "# Findings index",
    "",
    "| finding | receipt | date |",
    "|---|---|---|",
    "| **Kolibri-1 runs on 4x P100 through the unofficial port** at 9.1 tok/s | `kolibri-194/RESULT_K1.md` | 10-01 |",
    "| Prompt-cache reuse changes temp-0 output | `hermesagent20/PREFIX_CACHE.md` | 07-27 |",
    "| **Kolibri sliding window is wrong in port 2**, fixed later | `kolibri-194/RESULT_K9.md` | 10-20 |",
]


def precheck_output(*rows):
    """What ledger_precheck prints for INDEX.md hits, given 1-based INDEX_ROWS line numbers."""
    lines = ["terms: x", "", "=== INDEX.md ==="]
    lines += [f"  [2 terms] L{n}: {INDEX_ROWS[n - 1][:300]}" for n in rows]
    return "\n".join(lines + ["", "PRIOR ART FOUND -- read the receipts above BEFORE designing the experiment."])


@pytest.fixture
def index(tmp_path, monkeypatch):
    p = tmp_path / "INDEX.md"
    p.write_text("\n".join(INDEX_ROWS) + "\n")
    monkeypatch.setattr(pc, "INDEX", p)
    monkeypatch.setattr(pc, "_LINES", None)
    monkeypatch.setattr(pc, "_DF", {})
    return p


@pytest.fixture
def stub(monkeypatch, index):
    """Replace ledger_precheck. Set .result = (exit code, stdout); .seen records the queries."""
    class S:
        result = (0, "No prior art found for those terms.")
        seen = []
    def fake(q):
        S.seen.append(q)
        return S.result
    monkeypatch.setattr(pc, "precheck", fake)
    return S


def prereg(tmp_path, field, name="PREREG_KOLIBRI_SPEED.md", date="2026-10-06"):
    p = tmp_path / "kolibri-194" / name
    p.parent.mkdir(parents=True, exist_ok=True)
    body = [
        "# Pre-registration -- does Kolibri-1 run correctly on 4x P100 through the unofficial port?",
        "",
        f"**Registered {date}, before any row.** Kolibri sliding window and port speed.",
        "",
    ]
    if field is not None:
        body += [f"**Prior art checked:** {field}", ""]
    body += ["## Arms", "", "- K1: port 1, Kolibri Q4_K_M."]
    p.write_text("\n".join(body) + "\n")
    return p


def test_field_present_nothing_found_and_nothing_exists(tmp_path, stub, capsys):
    p = prereg(tmp_path, '`ledger_precheck.py "Kolibri"` -> nothing found.')
    stub.result = (0, "No prior art found for those terms.")
    assert pc.main([str(p)]) == 0
    assert stub.seen, "a nothing-found claim must be checked against the index"
    assert "ok" in capsys.readouterr().out


def test_field_missing(tmp_path, stub, capsys):
    p = prereg(tmp_path, None)
    assert pc.main([str(p)]) == 1
    out = capsys.readouterr().out
    assert "MISSING" in out and "Prior art checked" in out
    assert not stub.seen, "no field, nothing to check against"


def test_nothing_found_but_index_has_prior_art(tmp_path, stub, capsys):
    p = prereg(tmp_path, '`ledger_precheck.py "Kolibri"` -> nothing found.')
    stub.result = (2, precheck_output(5))
    assert pc.main([str(p)]) == 2
    out = capsys.readouterr().out
    assert "PRIOR-ART?" in out
    assert "INDEX.md L5: Kolibri-1 runs on 4x P100" in out and "kolibri-194/RESULT_K1.md" in out
    assert all(len(l) < 200 for l in out.splitlines()), "one short line per hit"


def test_field_acknowledges_prior_art(tmp_path, stub, capsys):
    p = prereg(tmp_path, '`ledger_precheck.py "Kolibri port"` -> receipts found: `kolibri-194/RESULT_K1.md` (9.1 tok/s). '
                         "**What this adds:** the second port.")
    stub.result = (2, precheck_output(5))
    assert pc.main([str(p)]) == 0
    assert not stub.seen, "an acknowledged field is not second-guessed"
    assert "PRIOR-ART?" not in capsys.readouterr().out


def test_hits_after_registration_are_not_prior_art(tmp_path, stub):
    """A finding indexed after the prereg was written (often its own result) could not have been seen."""
    p = prereg(tmp_path, '`ledger_precheck.py "Kolibri"` -> nothing found.', date="2026-10-06")
    stub.result = (2, precheck_output(7))   # dated 10-20
    assert pc.main([str(p)]) == 0


def test_precheck_exit_code_decides(tmp_path, stub):
    """Rows in the output do not count if ledger_precheck itself says nothing was found."""
    p = prereg(tmp_path, "nothing.")
    stub.result = (0, precheck_output(5))
    assert pc.main([str(p)]) == 0


def test_field_parsing():
    assert pc.field("# T\n\nno field here\n") is None
    assert pc.field("**Prior art checked:** a\ncontinued\n\n## Next\n") == "a continued"
    lst = "- **Prior art checked:** x -> nothing on Y.\n  more of it\n- **Next item:** receipts RESULT_Z.md\n"
    assert pc.field(lst) == "x -> nothing on Y. more of it"


@pytest.mark.parametrize("text,claims", [
    ('`ledger_precheck.py "Nanbeige"` -> nothing found.', True),
    ('`ledger_precheck.py "Spite"` -> nothing on Spite.', True),
    ("-> no prior art.", True),
    ('-> receipts found: `x/RESULT_A.md`; nothing on threads.', False),
    ("-> nothing on calibration; INDEX L305 is adjacent.", False),
    ("-> the Ornith-1.5-9B receipts (spec decoding); nothing on calibration.", False),
    ("checked the stored arms on this instrument.", False),
])
def test_claims_nothing(text, claims):
    assert pc.claims_nothing(text) is claims


def test_queries_use_rare_title_terms(tmp_path, index):
    p = prereg(tmp_path, "nothing.")
    qs = pc.queries(p.read_text())
    assert qs and "kolibri" in qs[0]
    assert all(w not in pc.GENERIC for q in qs for w in q.split())


def test_summary_counts_only(tmp_path, stub, capsys):
    a = prereg(tmp_path, None, name="PREREG_A.md")
    b = prereg(tmp_path, '-> receipts found: `kolibri-194/RESULT_K1.md`.', name="PREREG_B.md")
    c = prereg(tmp_path, "-> nothing found.", name="PREREG_C.md")
    stub.result = (2, precheck_output(5))
    assert pc.main([str(a), str(b), str(c), "--summary"]) == 2
    out = capsys.readouterr().out.strip().splitlines()
    assert out == ["3 preregs: 1 lack the prior-art field, 1 may have unacknowledged prior art, 1 pass"]


def test_registered_date():
    assert pc.registered("**Registered 2026-10-06, before any row.**") == datetime.date(2026, 10, 6)
    assert pc.registered("no date") is None


def test_real_precheck_runs_offline_against_this_checkout():
    """The unstubbed path imports ledger_precheck and re-points it at the repo (its own ROOT is /mnt)."""
    rc, out = pc.precheck("prompt cache determinism")
    assert rc in (0, 2) and "terms:" in out
    assert "/mnt/" not in out


def test_hook_printer_prints_and_installs_nothing():
    r = subprocess.run(["bash", str(ROOT / "tools" / "install_prereg_hook.sh")], capture_output=True, text=True)
    assert r.returncode == 0
    assert "prereg_check.py --staged" in r.stdout and "/home/" not in r.stdout


def test_filename_hit_needs_a_whole_word(monkeypatch, index):
    """2026-11-02: "ports" in a query matched SPECTRAL_REPORTS.md by substring; a real filename term still counts."""
    monkeypatch.setattr(pc, "_added", lambda p: datetime.date(2026, 9, 1))
    out = "=== FILENAME matches\n  data/receipts/scale-gfx1201/drafts/SPECTRAL_REPORTS.md\n  data/receipts/kolibri-old/RESULT_KOLIBRI.md\n"
    got = pc.hits(out, datetime.date(2026, 10, 6), "data/receipts/kolibri-194/PREREG_KOLIBRI_194.md", query="port ports kolibri")
    assert got == ["receipt data/receipts/kolibri-old/RESULT_KOLIBRI.md"]
