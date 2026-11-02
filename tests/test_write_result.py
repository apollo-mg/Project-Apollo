"""write_result.py (RESULT draft from committed files) on small synthetic fixtures under tmp_path: a clean run, an ABORT,
a missing state.log, a missing scorecard row, and refusing a hand-written RESULT. tmp_path is not a git repo, so every
source reads 'not committed'; that is the draft telling the truth, and the tests check it."""
import builtins, csv, hashlib, json
from pathlib import Path
import pytest
import write_result, abstend

MID = "toy-1b"
RECIPE = {"schema": "abstend-recipe/1", "model_id": MID, "model": {"display": "Toy-1B"},
          "file": {"repo": "acme/Toy-1B", "revision": "abc1234", "name": "Toy-1B-Q8_0.gguf", "sha256": "1" * 64, "store": "/mnt/x", "quant": "Q8_0"},
          "host": "9070", "engine": {"name": "llama.cpp", "commit": "f74e2fa", "build": "build_rocm", "bin": "/mnt/x/llama-server", "flags": "-ngl 99 --cache-ram 0", "weights": "store"},
          "modes": {"greedy": {"arm": "TOYG", "thinking": False, "max_tokens": 1024, "timeout": 600, "primary": True},
                    "vendor": {"arm": "TOYV", "thinking": True, "max_tokens": 8192, "timeout": 600, "primary": False, "sampling": {"temperature": 0.6}}},
          "instruments": ["M1-v1", "AbstentionBench-sub1000/norefs"], "abench": {"arm": "TOYAB"}}
CLEAN = """2026-11-01 10:00:00 chain start
2026-11-01 10:00:00 desktop: kernel 7.3.0-4-cachyos; linux-firmware-amdgpu 1:20261019-1 mesa 3:26.2.5-1
guard OK
2026-11-01 10:00:10 model sha256 ok at the store
2026-11-01 10:00:10 MemAvailable 20 GiB, SwapFree 28 GiB
2026-11-01 10:00:15 server up pid 1: /mnt/x/Toy-1B-Q8_0.gguf
defaults audit: identical with and without explicit neutral penalties
TOYG smoke OK: content '4721', reasoning 0 chars
2026-11-01 10:05:00 TOYG rc=0 rows=240
TOYV smoke OK: content '4721', reasoning 80 chars
2026-11-01 10:30:00 TOYV rc=0 rows=240
2026-11-01 10:30:00 sub1000 verified against its frozen question hashes
2026-11-01 11:00:00 TOYAB subject rc=0 rows=1000 errors=0
2026-11-01 11:10:00 TOYAB judge norefs rc=0 rows=1000
verdicts_TOYAB.csv: 1000 of 1000 items judged, 0 judge errors, 0 unparsed
2026-11-01 11:10:01 verdicts rc=0
2026-11-01 11:10:02 scorecard rc=0
2026-11-01 11:10:02 DONE
2026-11-01 11:10:10 clef restored: active active
"""
HEAD = ["config_id", "model_id", "quant", "thinking", "decoding", "instrument", "metric", "value", "ci_lo", "ci_hi", "n", "receipt"]


def row(cfg, metric, v, lo, hi, n, inst="M1-v1", mid=MID):
    return [cfg, mid, "Q8_0", "off", "greedy", inst, metric, v, lo, hi, n, "receipt.csv"]


ROWS = [row("m1:TOYG", "knowledge.hard_acc", "0.42", "0.3264", "0.5199", "100"), row("m1:TOYG", "reliability.unfinished", "0.0", "0", "0.0158", "240"),
        row("m1:TOYV", "knowledge.hard_acc", "0.37", "0.2799", "0.4701", "100"),
        row("abench:TOYAB", "honesty.abstention_recall", "0.5721", "0.5253", "0.6176", "437", inst="AbstentionBench-sub1000/norefs"),
        row("m1:OTHER", "knowledge.hard_acc", "0.99", "0.9", "1.0", "100", mid="someone-else")]


@pytest.fixture
def repo(tmp_path):
    """A tmp repo: recipe, prereg naming the recipe's hash, state.log, scorecard.csv. Returns (root, recipe path, run dir)."""
    rp = tmp_path / "data/scorecard/recipes" / f"{MID}.json"; rp.parent.mkdir(parents=True); rp.write_text(json.dumps(RECIPE, indent=1))
    d = tmp_path / "data/receipts/abstend" / MID; d.mkdir(parents=True)
    (d / f"PREREG_{MID}.md").write_text(f"# Pre-registration\n\n**Registered 2026-11-01, before any row.** From recipe (sha256:{hashlib.sha256(rp.read_bytes()).hexdigest()}).\n\n"
                                        "## Modes\n\n## Deviation 1 (2026-11-01 10:01, before any row): a toy deviation\n")
    (d / "chain_9070.sh").write_text("#!/bin/bash\n"); (d / "state.log").write_text(CLEAN)
    with open(tmp_path / "data/scorecard/scorecard.csv", "w", newline="") as f: w = csv.writer(f); w.writerow(HEAD); w.writerows(ROWS)
    return tmp_path, rp, d


def make(repo):
    root, rp, d = repo; out = write_result.write(rp, root, today="2026-11-02")
    return out.read_text()


def test_clean_run(repo, monkeypatch, capsys):
    root, rp, d = repo
    real = builtins.open, Path.read_text, Path.read_bytes   # the draft must never read a raw/ folder (gitignored, absent in the cloud)
    def no_raw(f):
        def g(p, *a, **k):
            assert "/raw/" not in str(p), p; return f(p, *a, **k)
        return g
    for obj, name, f in zip((builtins, Path, Path), ("open", "read_text", "read_bytes"), real): monkeypatch.setattr(obj, name, no_raw(f))
    (d / "raw").mkdir(); (d / "raw" / "trap.jsonl").write_text("{}\n")
    t = make(repo)
    assert (d / f"RESULT_{MID}.draft.md").exists() and not (d / f"RESULT_{MID}.md").exists()
    assert t.startswith("# RESULT (draft): Toy-1B Q8_0") and "registered 2026-11-01" in t and "which matches the recipe" in t
    assert f"sha256 `{hashlib.sha256(rp.read_bytes()).hexdigest()[:8]}...`" in t and "not committed" in t
    assert "- Deviation 1 (2026-11-01 10:01, before any row): a toy deviation" in t
    assert "1 launch in `state.log`, 2026-11-01 10:00:00 to 11:10:02 (DONE)" in t
    for l in ("    guard OK", "    2026-11-01 10:00:10 model sha256 ok at the store", "    TOYV smoke OK: content '4721', reasoning 80 chars",
              "    defaults audit: identical with and without explicit neutral penalties",
              "    2026-11-01 10:00:00 desktop: kernel 7.3.0-4-cachyos; linux-firmware-amdgpu 1:20261019-1 mesa 3:26.2.5-1",
              "    2026-11-01 11:00:00 TOYAB subject rc=0 rows=1000 errors=0"):
        assert l + "\n" in t, l
    assert "None in `state.log`: no `ABORT`" in t and "No kernel or firmware line" not in t
    assert "| knowledge.hard_acc | 0.42 | [0.3264, 0.5199] | 100 |" in t and "| knowledge.hard_acc | 0.37 | [0.2799, 0.4701] | 100 |" in t
    assert "### greedy (arm `TOYG`, primary)" in t and "### vendor (arm `TOYV`)" in t
    assert "Instrument AbstentionBench-sub1000/norefs;" in t and "| honesty.abstention_recall | 0.5721 | [0.5253, 0.6176] | 437 |" in t
    assert "0.99" not in t and "server up" not in t and "**Missing:**" not in t
    assert t.rstrip().endswith("## Interpretation\n\n_To be written by a human. This draft states facts and numbers only._")
    assert "/home/" not in t and f"data/receipts/abstend/{MID}/RESULT_{MID}.draft.md" in capsys.readouterr().out


def test_abort_quoted_verbatim(repo):
    root, rp, d = repo
    (d / "state.log").write_text("2026-11-01 09:00:00 chain start\nguard OK\n2026-11-01 09:00:05 ABORT: model sha256 mismatch at the store (deadbeef)\n" + CLEAN.replace(
        "TOYAB judge norefs rc=0", "TOYAB judge norefs rc=1").replace("2026-11-01 10:30:00 sub1000 verified against its frozen question hashes\n",
                                                                       "2026-11-01 10:30:00 AbstentionBench SKIPPED: sub1000 failed its hash verification (raw/TOYAB.chain.log)\n"))
    t = make(repo); dev = t.split("## Deviations")[1].split("## Card")[0]
    assert "2 launches in `state.log`, 2026-11-01 09:00:00 to 2026-11-01 11:10:02 (DONE)" not in t   # same day: time only
    assert "2 launches in `state.log`, 2026-11-01 09:00:00 to 11:10:02 (DONE)" in t
    assert "**Launch 1:** 2026-11-01 09:00:00 to 09:00:05 (last timestamped line; **no DONE line**)" in t
    assert "    [launch 1] 2026-11-01 09:00:05 ABORT: model sha256 mismatch at the store (deadbeef)\n" in dev
    assert "    [launch 2] 2026-11-01 10:30:00 AbstentionBench SKIPPED: sub1000 failed its hash verification (raw/TOYAB.chain.log)\n" in dev
    assert "    [launch 2] 2026-11-01 11:10:00 TOYAB judge norefs rc=1 rows=1000\n" in dev
    assert "rc=0" not in dev and "errors=0" not in dev and "None in" not in dev


def test_missing_state_log(repo):
    root, rp, d = repo; (d / "state.log").unlink()
    t = make(repo)
    assert "**Run:** **Missing:** `state.log`." in t and f"**Missing:** `{MID}/state.log`." in t and "Not known: `state.log` is missing." in t
    assert "| knowledge.hard_acc | 0.42 |" in t and t.rstrip().endswith("numbers only._")


def test_missing_scorecard_row_and_files(repo):
    root, rp, d = repo
    with open(root / "data/scorecard/scorecard.csv", "w", newline="") as f: w = csv.writer(f); w.writerow(HEAD); w.writerows(r for r in ROWS if r[0] != "m1:TOYV")
    (d / f"PREREG_{MID}.md").unlink(); (d / "chain_9070.sh").unlink()
    t = make(repo)
    assert f"**Missing:** no `m1:TOYV` rows for `{MID}` in `scorecard.csv`." in t and "| knowledge.hard_acc | 0.42 |" in t
    assert f"**Missing:** `PREREG_{MID}.md`" in t and "**Missing:** no `chain_*.sh`." in t
    (root / "data/scorecard/scorecard.csv").unlink(); t = make(repo)
    assert "**Missing:** `data/scorecard/scorecard.csv`." in t and "### greedy" not in t


def test_prereg_hash_mismatch_is_stated(repo):
    root, rp, d = repo; rp.write_text(rp.read_text() + "\n")   # recipe changed after the prereg
    assert "**which does not match the recipe**" in make(repo)


def test_refuses_hand_written_result(repo, capsys):
    root, rp, d = repo; final = d / f"RESULT_{MID}.md"; final.write_text("# RESULT: hand-written\n")
    with pytest.raises(SystemExit, match="refused: .*RESULT_toy-1b.md exists"):
        write_result.write(rp, root)
    assert final.read_text() == "# RESULT: hand-written\n" and not (d / f"RESULT_{MID}.draft.md").exists()
    assert write_result.write(rp, root, stdout=True) is None and "# RESULT (draft): Toy-1B" in capsys.readouterr().out
    assert final.read_text() == "# RESULT: hand-written\n"


def test_abstend_result_subcommand(repo, monkeypatch):
    """abstend.py result RECIPE validates the recipe, then hands it to write_result with abstend's ROOT."""
    root, rp, d = repo; seen = []
    monkeypatch.setattr(abstend, "ROOT", root); monkeypatch.setattr(write_result, "write", lambda p, r, s: seen.append((Path(p), r, s)))
    monkeypatch.setattr("sys.argv", ["abstend.py", "result", str(rp), "--stdout"]); abstend.main()
    assert seen == [(rp, root, True)]


def test_committed_names_added_and_last_commit(tmp_path):
    """committed(): the registering commit, the last one when later commits appended to the file, and uncommitted edits."""
    import subprocess
    g = lambda *a: subprocess.run(["git", "-C", str(tmp_path), "-c", "user.name=t", "-c", "user.email=t@example.invalid", *a], check=True, capture_output=True)
    f = tmp_path / "PREREG_x.md"; f.write_text("a\n"); g("init", "-q"); g("add", "."); g("commit", "-qm", "register")
    added = subprocess.run(["git", "-C", str(tmp_path), "log", "--abbrev=8", "--format=%h"], capture_output=True, text=True).stdout.split()[0]
    assert write_result.committed(f, tmp_path) == f"added `{added}`"
    f.write_text("a\nb\n"); assert write_result.committed(f, tmp_path) == f"added `{added}`, **modified since**"
    g("commit", "-qam", "deviation 1"); last = subprocess.run(["git", "-C", str(tmp_path), "log", "-1", "--abbrev=8", "--format=%h"], capture_output=True, text=True).stdout.strip()
    assert write_result.committed(f, tmp_path) == f"added `{added}`, last changed `{last}`"
    assert write_result.committed(tmp_path / "new.md", tmp_path) == "not committed"
