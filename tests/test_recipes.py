"""Recipe validation (abstend.validate) and the registry merge (abstend.load_recipes)."""
import json
import pytest
import abstend
from conftest import RECIPES, SC, load


def test_committed_recipes_validate():
    assert sorted(rc["model_id"] for _, rc in abstend.recipes()) == ["llama-3.1-8b-instruct", "nanbeige4.3-33b", "phi-4-mini"]


def errors(rc):
    """validate's error list; [] when it passes. The path is the recipe's own name, so the file-name rule stays quiet."""
    try: abstend.validate(rc, f"{rc['model_id']}.json")
    except SystemExit as e: return str(e).split(": ", 1)[1].split("; ")
    return []


def _drop_greedy(rc): del rc["modes"]["greedy"]; rc["modes"]["vendor"]["primary"] = True
def _two_primaries(rc): rc["modes"]["vendor"]["primary"] = True
def _greedy_sampling(rc): rc["modes"]["greedy"]["sampling"] = {"temperature": 0.7}
def _short_sha(rc): rc["file"]["sha256"] = rc["file"]["sha256"][:12]
def _home_path(rc): rc["file"]["store"] = "/".join(("", "home", "someone", "models"))   # in pieces: no such literal in a public repo
def _unknown_instrument(rc): rc["instruments"].append("M2-v9")
def _thinking_abench(rc): rc["abench"]["template_kwargs"] = {"enable_thinking": True}
def _no_cache_ram(rc): rc["engine"]["flags"] = rc["engine"]["flags"].replace(" --cache-ram 0", "")
def _bad_schema(rc): rc["schema"] = "abstend-recipe/0"
def _unknown_host(rc): rc["host"] = "42"
def _third_mode(rc): rc["modes"]["creative"] = {**rc["modes"]["vendor"], "primary": False}
def _unknown_mode_field(rc): rc["modes"]["greedy"]["seed"] = 1
def _bad_weights(rc): rc["engine"]["weights"] = "/tmp"
def _no_bin(rc): del rc["engine"]["bin"]
def _abench_no_arm(rc): del rc["abench"]["arm"]


# every rule fires alone: the base (llama, the recipe with both modes, the 9070 and AbstentionBench) is otherwise clean
BAD = [(_drop_greedy, "a greedy mode is required"), (_greedy_sampling, "the greedy mode cannot carry sampling"),
       (_two_primaries, "exactly one mode is primary"), (_short_sha, "file.sha256 must be the full 64-hex hash"),
       (_home_path, "no /home paths in a recipe (public repo)"),
       (_unknown_instrument, "instruments are M1-v1 and AbstentionBench-sub1000/norefs"),
       (_thinking_abench, "thinking-on AbstentionBench needs Meta's two-phase protocol, not in the pipeline yet"),
       (_no_cache_ram, "host 9070 requires --cache-ram 0 in engine.flags"), (_bad_schema, "schema is not abstend-recipe/1"),
       (_unknown_host, "host 42 not in hosts.json"), (_third_mode, "modes are greedy and vendor only"),
       (_unknown_mode_field, "unknown mode fields in L31G"), (_bad_weights, "engine.weights is /dev/shm (staged) or store"),
       (_no_bin, "engine.bin (the server binary on the host) is required"),
       (_abench_no_arm, "abench needs an arm (fields: arm, template_kwargs, primary, label, note)")]


@pytest.mark.parametrize("bad, msg", BAD, ids=[f.__name__[1:] for f, _ in BAD])
def test_validate_rejects(bad, msg):
    _, rc = load("llama-3.1-8b-instruct"); assert errors(rc) == []
    bad(rc); assert errors(rc) == [msg]


def test_validate_missing_key_and_file_name():
    _, rc = load("phi-4-mini"); del rc["engine"]
    with pytest.raises(SystemExit, match="missing engine"): abstend.validate(rc, "phi-4-mini.json")
    _, rc = load("phi-4-mini")
    with pytest.raises(SystemExit, match="file name must be <model_id>.json"): abstend.validate(rc, "phi4.json")


# REPORTED (PR description): validate() checks which mode fields are allowed, never which are required, and reads
# engine.flags unguarded. Such a recipe passes validation or dies with a KeyError instead of the named-rule SystemExit,
# and the KeyError comes later, from label()/run_argv() inside build_scorecard.py or chain.
def _mode_no_thinking(rc): del rc["modes"]["greedy"]["thinking"]
def _mode_no_arm(rc): del rc["modes"]["greedy"]["arm"]
def _no_flags(rc): del rc["engine"]["flags"]


@pytest.mark.parametrize("bad", [_mode_no_thinking, _mode_no_arm, _no_flags], ids=["mode_no_thinking", "mode_no_arm", "engine_no_flags"])
def test_validate_requires_fields(bad):
    _, rc = load("llama-3.1-8b-instruct"); bad(rc)
    with pytest.raises(SystemExit): abstend.validate(rc, f"{rc['model_id']}.json")


def empty(): return {"models": {}, "m1_arms": {}, "abench_arms": {}}


def test_load_recipes_merges():
    reg = abstend.load_recipes(empty())
    assert set(reg["models"]) == {json.load(open(p))["model_id"] for p in RECIPES}
    assert set(reg["m1_arms"]) == {"L31G", "L31V", "N33OFF", "N33THK", "PHI4MG"}
    assert reg["m1_arms"]["N33THK"] == {"model": "nanbeige4.3-33b", "quant": "Q8_0", "thinking": "on (T 0.6)", "primary": False, "note": ""}
    assert reg["m1_arms"]["L31G"]["thinking"] == "off" and reg["m1_arms"]["L31G"]["primary"]
    assert reg["abench_arms"] == {"L31AB": {"model": "llama-3.1-8b-instruct", "quant": "Q8_0", "primary": False, "note": "pipeline run 2; reproduces LLAMA8 on sub1000",
                                            "thinking": "n/a", "verdicts": "verdicts_L31AB.csv", "col": "norefs", "sub1000_only": True}}


def test_load_recipes_with_committed_registry():   # what build_scorecard.py does
    reg = abstend.load_recipes(json.load(open(SC / "registry.json")))
    assert "phi-4-mini" in reg["models"] and "LLAMA8" in reg["abench_arms"] and "L31AB" in reg["abench_arms"]


@pytest.mark.parametrize("table, key, msg", [("models", "phi-4-mini", "model phi-4-mini is also in registry.json"),
                                             ("m1_arms", "N33THK", "arm N33THK is already registered"),
                                             ("abench_arms", "L31AB", "AbstentionBench arm L31AB is already registered")])
def test_load_recipes_refuses_duplicates(table, key, msg):
    reg = empty(); reg[table][key] = {}
    with pytest.raises(SystemExit, match=msg): abstend.load_recipes(reg)
