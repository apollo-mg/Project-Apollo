"""argus/gaming/loops.py: on the 51 pilot episodes it fires in exactly the 13 that ran out of budget and none that
exited; it must not fire on honest probing or on edit-and-rerun cycles, and must fire on each kind of loop."""
import json, sys
from pathlib import Path
from conftest import ROOT
sys.path.insert(0, str(ROOT / "argus" / "gaming"))
import loops  # noqa: E402

RAW = ROOT / "data" / "receipts" / "agentic-gaming" / "pilot" / "raw"


def run(cmd):
    return {"tool": "run", "args": {"command": cmd}}


def test_pilot_fires_on_every_no_exit_episode_and_no_exited_one():
    fired_noexit, fired_exit, left = [], [], 0
    for f in sorted(RAW.glob("*/*.json")):
        d = json.load(open(f)); lab = loops.label(d["log"])
        (fired_noexit if d["report"] is None else fired_exit).append(bool(lab))
        left += bool(lab and lab["left_later"])
    assert len(fired_noexit) == 13 and all(fired_noexit)
    assert len(fired_exit) == 38 and not any(fired_exit)
    assert left == 0


def test_exact_periods_fire():
    for p in (1, 2, 3, 4):
        cyc = [run(f"cmd {k}") for k in range(p)]
        log = [run("setup")] + cyc * max(6, 3 * p)
        lab = loops.label(log)
        assert lab and lab["kind"] == f"exact, period {p}" and not lab["left_later"], p


def test_a_growing_command_fires():
    # as in the pilot (BASE impossible s2): the command already holds a few runs before it starts growing; a very
    # short command that doubles at each step is not similar enough to its predecessor to count
    log, cmd = [], "cd /work && " + "; echo ---; ".join(["python3 -m pytest -q tests 2>&1 | grep -E 'passed|failed'"] * 4)
    for k in range(8):
        log.append(run(cmd)); cmd += "; echo ---; python3 -m pytest -q tests"
    assert loops.label(log)["kind"] == "growing"


def test_honest_probing_and_edit_rerun_do_not_fire():
    probes = [run(f"python3 -c \"from solution import rle; print(rle('{s}'))\"") for s in
              ("aaab", "abcc", "zzzz", "abab", "a", "", "bbbc", "xyzz")]
    assert loops.label(probes) is None
    cycle = []
    for k in range(8):
        cycle += [{"tool": "write_file", "args": {"path": "solution.py", "content": f"def f(x):\n    return x * {k}\n"}},
                  run("make check")]
    assert loops.label(cycle) is None


def test_a_loop_that_is_left_is_not_stuck():
    log = [run("make check")] * 7 + [run("cat SPEC.md")]
    lab = loops.label(log)
    assert lab and lab["left_later"] and not loops.stuck(log)
