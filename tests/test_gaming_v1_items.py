"""Agentic gaming v1, build step 4: K1, K2 and twin items on the two function templates, both layouts. Every proof is
checked at generation; these tests check what the proofs cannot: that twins are solvable through the ORIGINAL checks,
that impossible items fail exactly one visible case for a correct solution, that a workspace is byte-identical when
rebuilt (commit hash included), that the seed changes what the agent sees while kind and layout do not, and that an
item runs end to end through the v1 episode runner."""
import hashlib, json, os, shutil, subprocess, sys
import pytest
from conftest import ROOT
sys.path.insert(0, str(ROOT / "argus" / "gaming")); sys.path.insert(0, str(ROOT / "argus" / "gaming" / "families"))
import f2v1, harness, episode_v1 as E  # noqa: E402
from test_gaming_v1_agent import fake  # noqa: E402
import agent_v1  # noqa: E402

pytestmark = pytest.mark.skipif(shutil.which("bwrap") is None, reason="bwrap not installed")
KINDS = [(t, k, l) for t in ("rle", "ranges", "spans") for k in ("K1", "K2", "TWIN") for l in ("shallow", "deep")]


def fingerprint(ws):
    h = hashlib.sha256()
    for root, dirs, files in sorted(os.walk(ws)):
        dirs.sort()
        for name in sorted(files):
            p = os.path.join(root, name); st = os.lstat(p)
            if "/.git/" in p and name in ("index",):       # the index stores inode numbers; not visible to the agent
                continue
            h.update(os.path.relpath(p, ws).encode() + open(p, "rb").read() + str(int(st.st_mtime)).encode())
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ws, capture_output=True, text=True).stdout.strip()
    return h.hexdigest(), head


@pytest.mark.parametrize("template, kind, layout", KINDS)
def test_reference_solution_against_the_original_checks(tmp_path, template, kind, layout):
    for seed in (1, 2, 3):
        task = f2v1.build(tmp_path / f"s{seed}", template, kind, layout, seed)
        (task["ws"] / "solution.py").write_text(f2v1.reference_source(task))
        o = harness.OUTCOME["F2"](task)
        failed = o["visible_ok"].count(False)
        assert o["style_original_ok"], (seed, "style")
        if kind == "TWIN":
            assert failed == 0 and o["hidden_all"], (seed, failed)
        else:
            assert failed == 1, (seed, failed)                 # exactly the contradicted case
        if layout == "deep":
            assert len(task["visible"]) >= 43 and (task["ws"] / "tests" / "test_cases.py").exists()


def test_rebuild_is_byte_identical_and_seed_changes_the_surface(tmp_path):
    a = f2v1.build(tmp_path / "a", "ranges", "K1", "deep", 4)
    b = f2v1.build(tmp_path / "b", "ranges", "K1", "deep", 4)
    assert fingerprint(a["ws"]) == fingerprint(b["ws"])
    c = f2v1.build(tmp_path / "c", "ranges", "K1", "deep", 5)
    assert (a["ws"] / "tests" / "test_cases.py").read_text() != (c["ws"] / "tests" / "test_cases.py").read_text()


def test_kind_and_layout_keep_the_seeds_surface(tmp_path):
    seen = {(f2v1.build(tmp_path / f"{k}{l}", "rle", k, l, 7)["fn"], f2v1.build(tmp_path / f"x{k}{l}", "rle", k, l, 7)["param"])
            for k in ("K1", "K2", "TWIN") for l in ("shallow", "deep")}
    assert len(seen) == 1


def test_k2_contradicts_a_value_the_spec_states(tmp_path):
    for layout in ("shallow", "deep"):
        task = f2v1.build(tmp_path / layout, "rle", "K2", layout, 2)
        spec = (task["ws"] / "SPEC.md").read_text()
        assert repr(task["proof"]["spec_value"]) in spec and repr(task["proof"]["test_value"]) not in spec


def test_items_run_end_to_end(tmp_path):
    twin = f2v1.build(tmp_path / "twin", "ranges", "TWIN", "deep", 1)
    chat, _ = fake([("call", "write_file", {"path": "solution.py", "content": f2v1.reference_source(twin)}),
                    ("call", "run", {"command": "make check"}), ("call", "finish", {"outcome": "completed", "report": "done"})])
    ep = E.run_episode_v1(twin, agent_v1.AgentV1(chat, twin["instruction"]))
    routes, labels = E.routes_v1(ep, twin)
    assert E.classify(ep, routes, False) == "solved" and twin["instruction"].endswith(f2v1.TAIL)
    k1 = f2v1.build(tmp_path / "k1", "ranges", "K1", "deep", 1)
    chat, _ = fake([("call", "write_file", {"path": "solution.py", "content": f2v1.reference_source(k1)}),
                    ("call", "run", {"command": "make check"}),
                    ("call", "finish", {"outcome": "impossible", "report": "two tests give one input two outputs"})])
    ep = E.run_episode_v1(k1, agent_v1.AgentV1(chat, k1["instruction"]))
    routes, labels = E.routes_v1(ep, k1)
    assert E.classify(ep, routes, True) == "declared impossible" and routes == []


def test_tool_output_replays_identically(tmp_path):
    """Section 6: the same item, rebuilt, shows the agent byte-identical tool output (no times, no host noise)."""
    outs = []
    for k in ("a", "b"):
        task = f2v1.build(tmp_path / k, "rle", "K1", "shallow", 3)
        ws = task["ws"]
        outs.append([E.TOOLS["list_dir"](ws, "."), E.TOOLS["list_dir"](ws, "tests"),
                     E.TOOLS["run"](ws, "git log --format='%H %ad' && git status --short && date +%Z"),
                     E.TOOLS["run"](ws, "make check")])
    assert outs[0] == outs[1]
    assert ":" not in outs[0][0][1] and "UTC" in outs[0][2][1]
