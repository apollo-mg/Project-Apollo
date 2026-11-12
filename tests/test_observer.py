"""tools/observer.py phase 1: every check against fakes (unit state, ssh, memory, disk, notifier) and a hand-driven
clock, in a temporary ops directory. Each alert must fire once per incident and clear when the incident does."""
import importlib.util, json, time
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location("observer", Path(__file__).resolve().parents[1] / "tools" / "observer.py")
ob = importlib.util.module_from_spec(spec); spec.loader.exec_module(ob)
T0 = 1_800_000_000.0


@pytest.fixture
def lab(tmp_path, monkeypatch):
    """A fake lab: a units dict, ssh/memory/disk switches, the alerts sent, a progress file and a log."""
    env = {"units": {}, "ssh": True, "mem": 20.0, "disk": 500.0, "sent": []}
    monkeypatch.setattr(ob, "OPS", tmp_path / "ops")
    monkeypatch.setattr(ob, "unit_state", lambda u: env["units"].get(u, ("inactive", "")))
    monkeypatch.setattr(ob, "ssh_ok", lambda h: env["ssh"])
    monkeypatch.setattr(ob, "mem_avail_gib", lambda: env["mem"])
    monkeypatch.setattr(ob, "disk_free_gb", lambda path="/": env["disk"])
    monkeypatch.setattr(ob, "notify", lambda kind, title, body, prio="default": env["sent"].append((kind, title, prio)) or "fake")
    env["rows"] = tmp_path / "rows.jsonl"; env["rows"].write_text('{"header": true}\n')
    env["log"] = tmp_path / "chain.log"; env["log"].write_text("chain start\n")
    return env


def add(env, n): env["rows"].write_text(env["rows"].read_text() + "".join('{"id": 1}\n' for _ in range(n)))


def watch(env, **kw):
    w = {"unit": "u1", "progress": [str(env["rows"])], "stall_min": 45, "log": str(env["log"]), "headers": 1, **kw}
    ob.save(ob.paths()[0], {"run": w})


def kinds(alerts): return [a["kind"] for a in alerts]


def test_stall_fires_once_and_clears_on_progress(lab):
    watch(lab); lab["units"]["u1"] = ("active", "")
    add(lab, 5); assert kinds(ob.check(T0)) == []
    assert kinds(ob.check(T0 + 30 * 60)) == []                 # 30 min without rows: under the limit
    assert kinds(ob.check(T0 + 50 * 60)) == ["stall"]          # 50 min: one alert
    assert kinds(ob.check(T0 + 80 * 60)) == []                 # still stalled: no repeat
    add(lab, 1); assert kinds(ob.check(T0 + 85 * 60)) == []    # progress clears it
    assert kinds(ob.check(T0 + 140 * 60)) == ["stall"]         # a new stall is a new incident


@pytest.mark.parametrize("tail, verdict, prio", [("2026-11-11 DONE\n", "finished", "low"), ("ABORT: hash mismatch\n", "failed", "high"),
                                                  ("something else\n", "ended", "low"), ("== DONE (0)\n", "finished", "low"),
                                                  ("ABORT: server died\n== DONE (1)\n", "failed", "high"),   # our chains' abort path
                                                  ("ABORT: a retried step\nretry ok\nDONE\n", "finished", "low")])   # the last word wins
def test_ended_reads_the_log_tail(lab, tail, verdict, prio):
    watch(lab); lab["units"]["u1"] = ("active", ""); ob.check(T0)
    lab["log"].write_text(lab["log"].read_text() + tail); lab["units"]["u1"] = ("inactive", "")
    a = [x for x in ob.check(T0 + 60) if x["kind"] == "ended"]
    assert len(a) == 1 and a[0]["title"] == f"run {verdict}" and a[0]["prio"] == prio
    assert not [x for x in ob.check(T0 + 120) if x["kind"] == "ended"]   # once


def test_new_error_lines_alert_once(lab):
    watch(lab); lab["units"]["u1"] = ("active", ""); add(lab, 1); ob.check(T0)
    lab["log"].write_text(lab["log"].read_text() + "ok line\nTraceback (most recent call last):\n")
    a = ob.check(T0 + 60); assert kinds(a) == ["logline"] and "Traceback" in a[0]["body"]
    assert kinds(ob.check(T0 + 120)) == []


def test_behind_schedule(lab):
    watch(lab, total=1000, deadline="2027-01-15T00:00:00")
    lab["units"]["u1"] = ("active", ""); add(lab, 10); ob.check(T0)
    add(lab, 10)
    deadline_soon = ob.datetime.fromtimestamp(T0 + 3 * 3600).isoformat(timespec="seconds")
    watch(lab, total=1000, deadline=deadline_soon)   # re-written watch, same state file
    a = ob.check(T0 + 3600)   # 10 rows/h, 980 to go: about 98 h, deadline in 2 h
    assert kinds(a) == ["behind"]


def test_host_needs_two_failures_and_recovers(lab):
    watch(lab, host="194"); lab["units"]["u1"] = ("active", ""); add(lab, 1)
    lab["ssh"] = False
    assert kinds(ob.check(T0)) == [] and kinds(ob.check(T0 + 300)) == ["host"] and kinds(ob.check(T0 + 600)) == []
    lab["ssh"] = True; ob.check(T0 + 900); lab["ssh"] = False; ob.check(T0 + 1200)
    assert kinds(ob.check(T0 + 1500)) == ["host"]   # recovered in between: a new incident


def test_global_memory_and_disk(lab):
    lab["mem"], lab["disk"] = 2.0, 10.0
    assert sorted(kinds(ob.check(T0))) == ["disk", "memory"] and kinds(ob.check(T0 + 300)) == []
    lab["mem"] = 10.0; ob.check(T0 + 600); lab["mem"] = 2.0
    assert kinds(ob.check(T0 + 900)) == ["memory"]


def test_status_table_and_line(lab):
    watch(lab, total=100); lab["units"]["u1"] = ("active", ""); add(lab, 10); ob.check(T0); add(lab, 10); ob.check(T0 + 1800)
    line = ob.status(line=True, now=T0 + 1800)
    assert line.startswith("run active 20/100 20/h eta")
    assert "run" in ob.status(now=T0 + 1800).splitlines()[1]


def test_alerts_are_logged_and_state_persists(lab):
    watch(lab); lab["units"]["u1"] = ("active", ""); add(lab, 1); ob.check(T0); ob.check(T0 + 50 * 60)
    ev = [json.loads(l) for l in ob.paths()[2].read_text().splitlines()]
    assert [e["kind"] for e in ev] == ["stall"] and ev[0]["via"] == "fake"
    assert json.loads(ob.paths()[1].read_text())["run"]["sent"]["stall"] == T0 + 50 * 60


def test_a_failed_systemd_result_wins_over_the_log(lab):
    watch(lab); lab["units"]["u1"] = ("active", ""); ob.check(T0)
    lab["log"].write_text("DONE\n"); lab["units"]["u1"] = ("failed", "exit-code")
    a = [x for x in ob.check(T0 + 60) if x["kind"] == "ended"]
    assert a and a[0]["title"] == "run failed" and a[0]["prio"] == "high"
