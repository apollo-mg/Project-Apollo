"""Chain and prereg rendering through the --stdout paths (no guard, no git state, nothing written), plus the launch
guard in a throwaway git repo and the server-facing gates (smoke, audit) against a stubbed post()."""
import json, re, subprocess
import pytest
import abstend
from conftest import RECIPES, load

PLACEHOLDER = re.compile(r"@[A-Z_]+@")   # wider than chain()'s own check, which misses keys with an underscore


def render(capsys, p, rc):
    abstend.chain(p, rc, stdout=True); return capsys.readouterr().out


@pytest.mark.parametrize("p", RECIPES, ids=[p.stem for p in RECIPES])
def test_chain_renders(capsys, p):
    rc = json.load(open(p)); txt = render(capsys, p, rc)
    assert not PLACEHOLDER.search(txt)
    assert subprocess.run(["bash", "-n"], input=txt, text=True, capture_output=True).returncode == 0
    assert f"sha256:{abstend.sha(p)}" in txt and f"SHA={rc['file']['sha256']}" in txt
    for m in rc["modes"].values(): assert f"--arm {m['arm']}" in txt and f"raw/main_{m['arm']}.jsonl" in txt
    assert ("judge_abench.py" in txt) == (abstend.AB_INST in rc["instruments"])
    assert f"R={abstend.ROOT};" in txt   # the checkout the chain runs from, whatever it is


def test_chain_llama_judge_and_model_ports(capsys):
    p, rc = load("llama-3.1-8b-instruct"); txt = render(capsys, p, rc).splitlines()
    judge = [l for l in txt if l.lstrip().startswith("$JBIN -m")]; model = [l for l in txt if "$BIN -m $F" in l]
    assert len(judge) == 1 and len(model) == 1
    assert "/Meta-Llama-3.1-8B-Instruct-Q8_0.gguf" in judge[0] and "--port 8196" in judge[0]
    port = abstend.HOSTS["9070"]["url"].rsplit(":", 1)[1]
    assert port != "8196" and f"--port {port}" in model[0] and "--port 8196" not in model[0]


def test_chain_ssh_host(capsys):
    p, rc = load("nanbeige4.3-33b"); txt = render(capsys, p, rc)
    assert "S=mark@10.0.0.194" in txt and "--port 8190" in txt and "rsync -a $F $S:/dev/shm/" in txt
    assert '\\$HOME/llama.cpp-flint/build_sm60/bin/llama-server' in txt   # the remote readlink check expands ~ there
    assert "CUDA_VISIBLE_DEVICES=0,1,2,3 GGML_CUDA_ALLREDUCE=internal nohup" in txt


def test_chain_refuses_judge_url(monkeypatch):
    p, rc = load("phi-4-mini"); monkeypatch.setitem(abstend.HOSTS["9070"], "url", abstend.INSTRUMENTS[abstend.AB_INST]["judge"]["url"])
    with pytest.raises(SystemExit, match="the judge must not share the model's port"): abstend.chain(p, rc, stdout=True)


# FIXED 2026-10-29, reported by this suite: the port rule compares whole URLs, so the same port under another spelling of the same host passes
def test_chain_refuses_judge_port_by_another_name(monkeypatch):
    p, rc = load("phi-4-mini"); monkeypatch.setitem(abstend.HOSTS["9070"], "url", "http://localhost:8196")
    with pytest.raises(SystemExit, match="must not share"): abstend.chain(p, rc, stdout=True)


def test_chain_refuses_unfilled_placeholder(monkeypatch):
    p, rc = load("phi-4-mini"); monkeypatch.setattr(abstend, "TAIL", abstend.TAIL + "echo @NEWKEY@\n")
    with pytest.raises(SystemExit, match="unfilled placeholder @NEWKEY@"): abstend.chain(p, rc, stdout=True)


# FIXED 2026-10-29, reported by this suite: the leftover check is r"@[A-Z]+@", but the templates already use underscored keys (@PAUSE_START@)
def test_chain_refuses_unfilled_underscore_placeholder(monkeypatch):
    p, rc = load("phi-4-mini"); monkeypatch.setattr(abstend, "TAIL", abstend.TAIL + "echo @NEW_KEY@\n")
    with pytest.raises(SystemExit, match="unfilled placeholder"): abstend.chain(p, rc, stdout=True)


def test_chain_refusals(monkeypatch):
    p, rc = load("nanbeige4.3-33b"); rc["engine"]["weights"] = "store"
    with pytest.raises(SystemExit, match="ssh hosts serve from /dev/shm"): abstend.chain(p, rc, stdout=True)
    p, rc = load("nanbeige4.3-33b"); rc["host"] = "73"
    with pytest.raises(SystemExit, match="host 73 has no fixed test URL"): abstend.chain(p, rc, stdout=True)
    # without --stdout the guard decides, before anything is written
    p, rc = load("phi-4-mini"); monkeypatch.setattr(abstend, "guard", lambda *a, **k: False)
    monkeypatch.setattr(abstend, "chain_path", lambda rc: pytest.fail("chain got past a refused guard"))
    with pytest.raises(SystemExit) as e: abstend.chain(p, rc)
    assert e.value.code == 1


@pytest.mark.parametrize("p", RECIPES, ids=[p.stem for p in RECIPES])
def test_prereg_renders(capsys, no_precheck, p):
    rc = json.load(open(p)); abstend.prereg(p, rc, stdout=True); txt = capsys.readouterr().out
    assert f"`data/scorecard/recipes/{p.name}` (sha256:{abstend.sha(p)})" in txt   # what guard() looks for
    assert "**Prior art checked:** `ledger_precheck.py" in txt and no_precheck[0] == rc["model"]["display"]
    assert len(re.findall(r"^- \*\*(greedy|vendor)\*\* \(arm `", txt, re.M)) == len(rc["modes"])
    assert ("frozen norefs" in txt) == (abstend.AB_INST in rc["instruments"])
    assert rc["file"]["sha256"] in txt and "/home/" not in txt and not re.search(r"\{[a-z_]+\}", txt)


def test_prereg_is_never_rewritten(tmp_path, monkeypatch, no_precheck):
    p, rc = load("phi-4-mini"); pp = tmp_path / "PREREG_phi-4-mini.md"; monkeypatch.setattr(abstend, "prereg_path", lambda rc: pp)
    monkeypatch.setattr(abstend, "rel", lambda f: str(f))
    abstend.prereg(p, rc); assert pp.exists()
    with pytest.raises(SystemExit, match="a prereg is never rewritten"): abstend.prereg(p, rc)


def test_prior_queries_split_names(no_precheck):
    txt = abstend.prior("Phi-4-mini-instruct")
    assert no_precheck == ["Phi-4-mini-instruct", "Phi 4 mini instruct"] and txt.count("ledger_precheck.py") == 2
    no_precheck.clear(); abstend.prior("Nanbeige4.3"); assert no_precheck == ["Nanbeige4.3"]


@pytest.mark.parametrize("rc_, out, want", [(0, "", "nothing found."), (2, "INDEX.md:\n  hit one\n  hit two\n", "2 prior-art line(s) found"),
                                            (2, "only flat lines\n", "1 prior-art line(s) found")])
def test_precheck_exit_codes(monkeypatch, rc_, out, want):
    monkeypatch.setattr(abstend.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, rc_, out, ""))
    assert abstend.precheck("x").startswith(want)


def test_precheck_tool_failure(monkeypatch):
    monkeypatch.setattr(abstend.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 1, "", "boom"))
    with pytest.raises(SystemExit, match=r"ledger_precheck.py failed \(rc 1\): boom"): abstend.precheck("x")


def test_guard(tmp_path, monkeypatch):
    """guard() in a throwaway git repo standing in for ROOT: missing, uncommitted, modified, stale hash, OK."""
    monkeypatch.setattr(abstend, "ROOT", tmp_path); g = lambda *a: subprocess.run(["git", "-C", str(tmp_path), *a], check=True, capture_output=True)
    g("init", "-q"); commit = lambda: (g("add", "-A"), g("-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-qm", "x"))
    p, rc = load("phi-4-mini"); rp = tmp_path / "data/scorecard/recipes/phi-4-mini.json"; rp.parent.mkdir(parents=True); rp.write_text(p.read_text())
    pp = abstend.prereg_path(rc); assert pp == tmp_path / "data/receipts/abstend/phi-4-mini/PREREG_phi-4-mini.md"
    assert not abstend.guard(rp, rc, quiet=True)   # no prereg yet
    pp.parent.mkdir(parents=True); pp.write_text(f"plan for sha256:{abstend.sha(rp)}\n")
    assert not abstend.guard(rp, rc, quiet=True)   # not committed
    commit(); assert abstend.guard(rp, rc, quiet=True)
    pp.write_text(pp.read_text() + "edit\n"); assert not abstend.guard(rp, rc, quiet=True)   # modified since commit
    g("checkout", "--", "."); rp.write_text(rp.read_text().replace('"max_tokens": 1024', '"max_tokens": 2048')); commit()
    assert not abstend.guard(rp, rc, quiet=True)   # recipe changed after the prereg


def test_guard_messages(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(abstend, "ROOT", tmp_path); subprocess.run(["git", "-C", str(tmp_path), "init", "-q"], check=True)
    p, rc = load("phi-4-mini"); rp = tmp_path / "phi-4-mini.json"; rp.write_text(p.read_text())
    assert not abstend.guard(rp, rc)
    out = capsys.readouterr().out
    assert out.startswith("guard REFUSED: phi-4-mini.json not committed; data/receipts/abstend/phi-4-mini/PREREG_phi-4-mini.md missing")


@pytest.mark.parametrize("mode_edit, msg, ok", [({}, {"content": "4721"}, True), ({}, {"content": "4721", "reasoning_content": "hm"}, False),
                                                ({"thinking": True}, {"content": "4721", "reasoning_content": "hm"}, True),
                                                ({}, {"content": "341"}, False), ({}, {"content": None}, False)])
def test_smoke(monkeypatch, capsys, mode_edit, msg, ok):
    sent = []; monkeypatch.setattr(abstend, "post", lambda url, body, timeout=1800: sent.append((url, body)) or msg)
    _, rc = load("llama-3.1-8b-instruct"); rc["modes"]["greedy"].update(mode_edit)
    assert abstend.smoke(rc, "greedy") is ok
    url, body = sent[0]
    assert url == "http://127.0.0.1:8197/v1/chat/completions" and body["cache_prompt"] is False and body["temperature"] == 0 and "seed" not in body
    assert body["chat_template_kwargs"] == {"enable_thinking": bool(mode_edit.get("thinking"))}


def test_smoke_vendor_sends_sampling_and_seed(monkeypatch, capsys):
    sent = []; monkeypatch.setattr(abstend, "post", lambda url, body, timeout=1800: sent.append(body) or {"content": "4721"})
    _, rc = load("llama-3.1-8b-instruct"); assert abstend.smoke(rc, "vendor")
    assert sent[0]["temperature"] == 0.6 and sent[0]["top_p"] == 0.9 and sent[0]["seed"] == 1


@pytest.mark.parametrize("b, want", [("same", "identical with and without"), ("other", "DIFFERS")])
def test_audit(monkeypatch, capsys, b, want):
    import run_main
    sent = []; monkeypatch.setattr(abstend, "post", lambda url, body, timeout=1800: sent.append(body) or {"content": "same" if len(sent) == 1 else b})
    _, rc = load("phi-4-mini"); abstend.audit(rc)
    assert want in capsys.readouterr().out
    assert not set(run_main.NEUTRAL) & set(sent[0]) and sent[1] == {**sent[0], **run_main.NEUTRAL}


def test_chain_v2_sends_explicit_samplers(capsys):
    """Instrument v2 (2026-10-29): the subject run sends top_k 40 / min_p 0.05, so no GGUF-embedded default enters; v1 sends none."""
    p, rc = load("phi-4-mini"); rc["instruments"] = ["M1-v1", "AbstentionBench-sub1000v2/norefs"]; rc["abench"] = {"arm": "PHIV2"}
    assert "--neutral-penalties --top-k 40 --min-p 0.05" in render(capsys, p, rc)
    p, rc = load("phi-4-mini"); rc["instruments"] = ["M1-v1", "AbstentionBench-sub1000/norefs"]; rc["abench"] = {"arm": "PHIV1"}
    assert "--top-k" not in render(capsys, p, rc)


def test_one_abench_instrument_per_recipe():
    _, rc = load("phi-4-mini"); rc["instruments"] = ["M1-v1", "AbstentionBench-sub1000/norefs", "AbstentionBench-sub1000v2/norefs"]
    rc["abench"] = {"arm": "X"}
    with pytest.raises(SystemExit, match="one AbstentionBench instrument per recipe"): abstend.validate(rc, f"{rc['model_id']}.json")
