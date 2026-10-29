#!/usr/bin/env python3
"""Abstend pipeline, step one: a recipe (recipes/<model_id>.json) is the single record of a model's identity, the exact
file, the host and engine it is served on, and its run modes (greedy, plus the vendor's recommended sampling).
build_scorecard.py merges recipes through load_recipes(), so a recipe's model and arms must not also be in registry.json.

  check  RECIPE...    validate; derive each mode's run_main.py arguments and compare the header they would write with the
                      stored run's header, field by field (KNOWN_NEW fields allowed). Needs the project venv (httpx).
  args   RECIPE MODE  print the run_main.py command for one mode; refuses unless the launch guard passes
  prereg RECIPE       write the measurement-plan prereg to data/receipts/abstend/<model_id>/PREREG_<model_id>.md
                      (--stdout renders it without writing)
  guard  RECIPE       exit 0 only if the recipe and its prereg are committed, unmodified, and the prereg names this
                      recipe's hash
  chain  RECIPE       write the host's run chain to data/receipts/abstend/<model_id>/chain_<host>.sh and print the
                      systemd-run launch line (refuses unless the guard passes; --stdout renders it for review)
  smoke  RECIPE MODE  the pre-mode plumbing gate: the model echoes a number; thinking off -> no reasoning
  audit  RECIPE       defaults audit: one greedy request with and one without explicit neutral penalties, compared
  compare ARM ARM     item-by-item reproduction check of two stored M1 arms (content, finish, grade; P_abs to 1e-6)"""
import argparse, datetime, hashlib, json, re, shlex, subprocess, sys, urllib.request
from pathlib import Path
HERE = Path(__file__).resolve().parent; ROOT = HERE.parents[1]; QA = ROOT / "data" / "receipts" / "quant-abstention"
HOSTS = json.load(open(HERE / "hosts.json"))
SCHEMA = "abstend-recipe/1"
KNOWN_NEW = {"neutral_penalties", "meta.recipe"}    # fields the pipeline adds that hand-run arms never wrote
HDR_RUNTIME = {"header", "variant_ids", "render_tail", "props", "started"}   # written by the server, not the arguments


def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def rel(p): return str(Path(p).resolve().relative_to(ROOT))


def validate(rc, path):
    err = []
    if rc.get("schema") != SCHEMA: err.append(f"schema is not {SCHEMA}")
    for k in ("model_id", "model", "file", "host", "engine", "modes", "instruments"):
        if k not in rc: err.append(f"missing {k}")
    if err: raise SystemExit(f"{path}: " + "; ".join(err))
    if Path(path).stem != rc["model_id"]: err.append("file name must be <model_id>.json")
    if not re.fullmatch(r"[0-9a-f]{64}", rc["file"].get("sha256", "")): err.append("file.sha256 must be the full 64-hex hash")
    if rc["host"] not in HOSTS: err.append(f"host {rc['host']} not in hosts.json")
    if "greedy" not in rc["modes"]: err.append("a greedy mode is required")
    if rc["modes"].get("greedy", {}).get("sampling"): err.append("the greedy mode cannot carry sampling")
    if set(rc["modes"]) - {"greedy", "vendor"}: err.append("modes are greedy and vendor only")
    if sum(bool(m.get("primary")) for m in rc["modes"].values()) != 1: err.append("exactly one mode is primary")
    if "/home/" in json.dumps(rc): err.append("no /home paths in a recipe (public repo)")
    if "bin" not in rc["engine"]: err.append("engine.bin (the server binary on the host) is required")
    if rc["engine"].get("weights") not in ("/dev/shm", "store"): err.append("engine.weights is /dev/shm (staged) or store")
    for f in HOSTS.get(rc["host"], {}).get("require_flags", []):
        if f not in rc["engine"]["flags"]: err.append(f"host {rc['host']} requires {f} in engine.flags")
    for m in rc["modes"].values():
        if set(m) - {"arm", "thinking", "max_tokens", "timeout", "primary", "sampling", "sampling_source", "label", "note", "system", "template_kwargs", "no_think_check"}:
            err.append(f"unknown mode fields in {m.get('arm')}")
    if err: raise SystemExit(f"{path}: " + "; ".join(err))
    return rc


def recipes(paths=None):
    for p in paths or sorted((HERE / "recipes").glob("*.json")):
        yield Path(p), validate(json.load(open(p)), p)


def label(m):
    return m.get("label") or ("off" if not m["thinking"] else "on (vendor sampling)" if m.get("sampling") else "on")


def load_recipes(reg):
    """Merge every recipe's model and M1 arms into a registry dict (build_scorecard.py); duplicates are an error."""
    for p, rc in recipes():
        mid = rc["model_id"]
        if mid in reg["models"]: raise SystemExit(f"{p}: model {mid} is also in registry.json")
        reg["models"][mid] = rc["model"]
        if "M1-v1" not in rc["instruments"]: continue
        for m in rc["modes"].values():
            if m["arm"] in reg["m1_arms"]: raise SystemExit(f"{p}: arm {m['arm']} is already registered")
            reg["m1_arms"][m["arm"]] = {"model": mid, "quant": rc["file"]["quant"], "thinking": label(m), "primary": bool(m["primary"]), "note": m.get("note", "")}
    return reg


def meta(rc, path):
    f, e = rc["file"], rc["engine"]
    return {"model": f"{f.get('packager') or f['repo'].split('/')[0]} {f['name']} (sha256 {f['sha256'][:8]}..., rev {f['revision']})",
            "build": f"{e['name']} {e['commit']} {e['build']}", "placement": f"{e['flags']}, {e['weights']}",
            "recipe": f"{rel(path)} sha256:{sha(path)[:12]}"}


def run_argv(rc, path, mode):
    m = rc["modes"][mode]
    av = ["--url", HOSTS[rc["host"]]["url"] or "URL", "--arm", m["arm"], "--usage", "--neutral-penalties",
          "--max-tokens", str(m["max_tokens"]), "--timeout", str(m["timeout"]), "--meta", json.dumps(meta(rc, path))]
    if m["thinking"]: av.append("--thinking")
    if m.get("no_think_check"): av.append("--no-think-check")   # templates with no think block (Phi, Granite)
    if m.get("sampling"): av += ["--sampling", json.dumps(m["sampling"])]
    if m.get("system"): av += ["--system", m["system"]]
    if m.get("template_kwargs"): av += ["--template-kwargs", json.dumps(m["template_kwargs"])]
    return av


def flat(h):
    out = {k: v for k, v in h.items() if k not in HDR_RUNTIME and k != "meta"}
    out.update({f"meta.{k}": v for k, v in h.get("meta", {}).items()})
    return out


def check(paths):
    sys.path.insert(0, str(QA)); import run_main   # noqa: E402  (the runner's own parser and header mapping)
    bad = 0
    for p, rc in recipes(paths):
        for mode, m in rc["modes"].items():
            raw = QA / "raw" / f"main_{m['arm']}.jsonl"
            if not raw.exists(): print(f"{rc['model_id']} {mode} {m['arm']}: no stored run, nothing to compare"); continue
            got = flat(json.loads(open(raw).readline()))
            want = flat(run_main.header_fields(run_main.build_parser().parse_args(run_argv(rc, p, mode))))
            new = sorted(k for k in set(want) - set(got) if k in KNOWN_NEW)
            diff = sorted(k for k in set(want) | set(got) if k not in new and want.get(k, "<absent>") != got.get(k, "<absent>"))
            for k in diff: print(f"  MISMATCH {m['arm']} {k}: recipe {want.get(k, '<absent>')!r} != stored {got.get(k, '<absent>')!r}")
            bad += len(diff)
            print(f"{rc['model_id']} {mode} {m['arm']}: {len(got)} stored fields, {len(diff)} mismatches, new (allowed): {', '.join(new) or 'none'}")
    sys.exit(1 if bad else 0)


def prereg_path(rc): return ROOT / "data" / "receipts" / "abstend" / rc["model_id"] / f"PREREG_{rc['model_id']}.md"


def git(*a): return subprocess.run(["git", "-C", str(ROOT), *a], capture_output=True, text=True)


def guard(path, rc, quiet=False):
    pp = prereg_path(rc); why = []
    for f in (Path(path), pp):
        if not f.exists(): why.append(f"{rel(f) if f.is_relative_to(ROOT) else f} missing"); continue
        if git("ls-files", "--error-unmatch", rel(f)).returncode: why.append(f"{rel(f)} not committed")
        elif git("diff", "--quiet", "HEAD", "--", rel(f)).returncode: why.append(f"{rel(f)} modified since commit")
    if pp.exists() and f"sha256:{sha(path)}" not in pp.read_text(): why.append("prereg does not name this recipe's hash (recipe changed after the prereg)")
    if not quiet: print("guard " + ("OK" if not why else "REFUSED: " + "; ".join(why)))
    return not why


def precheck(q):
    r = subprocess.run([str(ROOT / "tools" / "ledger_precheck.py"), q], capture_output=True, text=True)
    if r.returncode == 0: return "nothing found."   # the tool's exit code decides (2 = prior art), never the parsing
    if r.returncode != 2: raise SystemExit(f"ledger_precheck.py failed (rc {r.returncode}): {r.stderr.strip()[-200:]}")
    hits = [l.strip() for l in r.stdout.splitlines() if l.startswith("  ") and l.strip()]   # index lines, filenames, search hits
    hits = hits or [l.strip() for l in r.stdout.splitlines() if l.strip()][:8]
    lines = "\n".join(f"  - {h[:160]}" for h in hits[:5])
    return f"{len(hits)} prior-art line(s) found; this run adds the standard card for this exact file and recipe.\n{lines}"


def prior(name):
    """The precheck tool takes a hyphenated name as ONE term (Phi-4-mini-instruct found nothing, 2026-10-28), so query
    the literal name and the name split on - and _, and report both."""
    qs = list(dict.fromkeys([name, re.sub(r"[-_]+", " ", name)]))
    return "\n".join(f"{'' if i == 0 else '- '}`ledger_precheck.py \"{q}\"` -> {precheck(q)}" for i, q in enumerate(qs))


def prereg(path, rc, force=False, stdout=False):
    pp = prereg_path(rc)
    if pp.exists() and not force and not stdout: raise SystemExit(f"{rel(pp)} exists (a prereg is never rewritten; --force only before any run)")
    f, e, h = rc["file"], rc["engine"], HOSTS[rc["host"]]
    modes = []
    for name, m in rc["modes"].items():
        dec = (f"sampled {json.dumps(m['sampling'])} ({m.get('sampling_source', 'vendor')}), per-item seed (20261025 + crc32(id)) mod 2^31"
               if m.get("sampling") else "greedy (temperature 0)")
        extra = "".join(f", {k} {json.dumps(m[k])}" for k in ("system", "template_kwargs") if m.get(k))
        modes.append(f"- **{name}** (arm `{m['arm']}`{', primary' if m['primary'] else ''}): thinking {'on' if m['thinking'] else 'off'}, "
                     f"{dec}, max_tokens {m['max_tokens']}, timeout {m['timeout']} s{extra}.")
    txt = f"""# Pre-registration -- {rc['model']['display']} {f['quant']}: Abstend standard card

**Registered {datetime.date.today().isoformat()}, before any row of this run.** Generated by `data/scorecard/abstend.py prereg` from
`{rel(path)}` (sha256:{sha(path)}). This is a measurement plan with a fixed analysis and no per-model predictions:
the standard card is the same for every model, and the launch guard refuses to run unless this file and the recipe
are committed unmodified.

**Prior art checked:** {prior(rc['model']['display'])}

## Artifact

- **File:** `{f['repo']}` rev `{f['revision']}`, `{f['name']}`, sha256 `{f['sha256']}`, verified at the store and again
  where it is served.
- **Host:** {h['desc']}.
- **Engine:** {e['name']} `{e['commit']}` {e['build']}; `{e['flags']}`; weights from {e['weights']}.

## Modes

{chr(10).join(modes)}

Every request sends `cache_prompt: false`. The generation request (R-gen) also sends explicit neutral penalties
(presence 0, frequency 0, repeat 1, DRY off), so no engine default enters; a vendor's own sampling values override them.
The answer-slot readout (R-slot) reads pre-sampling probabilities, which penalties cannot reach on llama.cpp. A smoke gate checks the plumbing,
not the model, before each mode: the model must echo a given number, and thinking-off reasoning must be empty.

## Instruments and fixed analysis

**Instruments:** {', '.join(rc['instruments'])}.

M1-v1 is 240 items (40 easy, 100 hard real, 100 invented), graded by `run_main.py`'s CAL
grader unchanged. The card (`build_scorecard.py`, Wilson 95 % intervals) reports per mode, over all items as frozen in
M1-v1: easy and hard accuracy, over-abstention on hard items, refusal of invented items (registered and lenient),
confabulation on invented items, and unfinished answers (cap hits and runaways; in these headline rates a runaway
counts as not answered). Beside them, the same easy, hard, lenient-refusal and confabulation rates among finished
answers only (`*_finished`, with n): the reading that does not count runaways against capability. Survivors skew
toward easier items, so these read high. Unfinished is also reported as its own reliability metric.

## Stop rules

A hash mismatch or a failed smoke gate stops the mode. A server death resumes on a fresh server (`run_main.py` skips
written ids), and is recorded in the result.
"""
    if stdout: return print(txt)
    pp.parent.mkdir(parents=True, exist_ok=True); pp.write_text(txt); print("wrote", rel(pp))


def post(url, body, timeout=1800):
    rq = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(rq, timeout=timeout).read())["choices"][0]["message"]


def smoke(rc, mode):
    m = rc["modes"][mode]; url = HOSTS[rc["host"]]["url"]
    # plumbing, not capability: Phi-4-mini answers 17*19 with 341 (pipeline run 1, 2026-10-28), so the gate is an echo
    body = {"messages": [{"role": "user", "content": "Reply with exactly this number and nothing else: 4721"}], "max_tokens": 4096, "temperature": 0,
            "cache_prompt": False, "chat_template_kwargs": {"enable_thinking": bool(m["thinking"])}, **(m.get("sampling") or {})}
    if m.get("sampling"): body["seed"] = 1
    msg = post(f"{url}/v1/chat/completions", body); c, r = msg.get("content") or "", msg.get("reasoning_content") or ""
    ok = "4721" in c and (m["thinking"] or not r)
    print(f"{m['arm']} smoke {'OK' if ok else 'FAILED'}: content {c[:80]!r}, reasoning {len(r)} chars"); return ok


def audit(rc):
    """What does the server add when a request omits penalties? Two greedy requests, identical but for explicit neutral
    penalties; different text means the engine injects a default (Strata, 2026-10-27) or is not deterministic."""
    sys.path.insert(0, str(QA)); from run_main import NEUTRAL   # noqa: E402
    url = HOSTS[rc["host"]]["url"]
    base = {"messages": [{"role": "user", "content": "Name three primary colors and one fact about each."}], "max_tokens": 96,
            "temperature": 0, "cache_prompt": False, "chat_template_kwargs": {"enable_thinking": False}}
    a, b = (post(f"{url}/v1/chat/completions", x).get("content") or "" for x in (base, {**base, **NEUTRAL}))
    print("defaults audit: " + ("identical with and without explicit neutral penalties" if a == b else
                                f"DIFFERS (an injected default, or nondeterminism): {a[:60]!r} vs {b[:60]!r}"))


def chain_path(rc): return prereg_path(rc).parent / f"chain_{rc['host']}.sh"


# Chain templates: @KEY@ placeholders, filled by chain(). The ssh variant follows nanbeige_chain.sh (2026-10-25).
HEAD = r"""#!/bin/bash
# Abstend chain: @RECIPE@ (sha256:@RHASH@) on host @HOST@. Generated by data/scorecard/abstend.py chain; regenerate it,
# never edit it. Launch:
#   @LAUNCH@
set -u
R=@ROOT@; PY=$R/venv_cachyos/bin/python3; Q=$R/data/receipts/quant-abstention; A=$R/data/scorecard/abstend.py
RC=$R/@RECIPE@; D=$R/@RUNDIR@; LOG=$D/state.log; F=@STORE@/@NAME@; N=@NAME@; SHA=@SHA@; H=@URL@
log () { echo "$(date '+%F %T') $*" >> $LOG; }
log "chain start"
[ "$(sha256sum $RC | cut -d' ' -f1)" = @RHASH@ ] || { log "ABORT: recipe changed since this chain was generated"; exit 1; }
$PY $A guard $RC >> $LOG 2>&1 || { log "ABORT: launch guard refused"; exit 1; }
got=$(sha256sum $F | cut -d' ' -f1); [ "$got" = $SHA ] || { log "ABORT: model sha256 mismatch at the store (${got:-none})"; exit 1; }
log "model sha256 ok at the store"
"""
LOCAL = r"""BIN=@BIN@
avail=$(awk '/MemAvailable/ {print int($2/1048576)}' /proc/meminfo)
[ "$avail" -ge @MINMEM@ ] || { log "ABORT: MemAvailable $avail GiB < @MINMEM@"; exit 1; }
log "MemAvailable $avail GiB, SwapFree $(awk '/SwapFree/ {print int($2/1048576)}' /proc/meminfo) GiB"
cleanup () {
  [ -n "${SP:-}" ] && [ "$(readlink /proc/$SP/exe 2>/dev/null)" = "$(readlink -f $BIN)" ] && kill $SP && timeout 60 tail --pid=$SP -f /dev/null
  systemctl --user start @PAUSE@; log "restored: $(systemctl --user is-active @PAUSE@ | tr '\n' ' ')"
}
trap cleanup EXIT
systemctl --user stop @PAUSE@; sleep 3
@ENV@$BIN -m $F @FLAGS@ --host 127.0.0.1 --port @PORT@ > $D/server.log 2>&1 < /dev/null & SP=$!
ok=0; for i in $(seq 1 120); do sleep 3; curl -s -m 3 $H/health | grep -q '"ok"' && { ok=1; break; }; done
[ $ok = 1 ] || { log "ABORT: server did not come up"; exit 1; }
log "server up pid $SP: $(curl -s $H/props | python3 -c 'import sys,json; print(json.load(sys.stdin)["model_path"])')"
"""
SSH = r"""S=@SSH@
cleanup () {
  ssh $S "P=\$(cat ~/abstend_server.pid 2>/dev/null); [ -n \"\$P\" ] && [ \"\$(readlink /proc/\$P/exe)\" = \"@RBIN@\" ] && kill \$P && timeout 60 tail --pid=\$P -f /dev/null; rm -f /dev/shm/$N"
  timeout 120 $R/@POWER@ off >> $LOG 2>&1; log "host powered off"
}
timeout 300 $R/@POWER@ on >> $LOG 2>&1
for i in $(seq 1 60); do ssh -o ConnectTimeout=5 -o BatchMode=yes $S true 2>/dev/null && break; sleep 10; done
trap cleanup EXIT
rsync -a $F $S:/dev/shm/ && got=$(ssh $S "sha256sum /dev/shm/$N" | cut -d' ' -f1)
[ "${got:-}" = $SHA ] || { log "ABORT: staged sha256 mismatch (${got:-none})"; exit 1; }
log "staged, sha256 ok; clocks $(ssh $S 'nvidia-smi --query-gpu=clocks.applications.graphics,power.limit --format=csv,noheader | tr "\n" " "')"
ssh $S "@ENV@nohup @BIN@ -m /dev/shm/$N @FLAGS@ --host 0.0.0.0 --port @PORT@ > ~/abstend_server.log 2>&1 < /dev/null & echo \$! > ~/abstend_server.pid"
ok=0; for i in $(seq 1 120); do sleep 5; curl -s -m 3 $H/health | grep -q '"ok"' && { ok=1; break; }; done
[ $ok = 1 ] || { log "ABORT: server did not come up"; exit 1; }
log "server up: $(ssh $S 'nvidia-smi --query-gpu=memory.used --format=csv,noheader | tr "\n" " "')"
"""
MODE = r"""if $PY $A smoke $RC @MODE@ >> $LOG 2>&1; then
  $PY -s run_main.py @ARGS@ >> $D/run_@ARM@.log 2>&1
  log "@ARM@ rc=$? rows=$(( $(wc -l < raw/main_@ARM@.jsonl) - 1 ))"; else log "@ARM@ SMOKE FAILED"; fi
"""
TAIL = r"""(cd $R/data/scorecard && $PY build_scorecard.py && $PY render_cards.py) >> $LOG 2>&1; log "scorecard rc=$?"
log "DONE"
"""


def chain(path, rc, stdout=False):
    h = HOSTS[rc["host"]]; e, f = rc["engine"], rc["file"]
    if not h.get("url"): raise SystemExit(f"host {rc['host']} has no fixed test URL in hosts.json")
    if h["kind"] == "ssh" and e["weights"] != "/dev/shm": raise SystemExit("ssh hosts serve from /dev/shm in this version")
    if not stdout and not guard(path, rc): sys.exit(1)
    cp = chain_path(rc); unit = f"abstend-{rc['model_id']}"
    launch = (f"systemd-run --user --unit={unit} --collect -p MemoryMax={h['memory_max']} -p ExecStopPost=\"systemctl --user start "
              f"{' '.join(h['pause'])}\" bash {cp}" if h["kind"] == "local" else f"systemd-run --user --unit={unit} --collect bash {cp}")   # absolute: systemd-run starts in ~
    sub = {"RECIPE": rel(path), "RHASH": sha(path), "HOST": rc["host"], "LAUNCH": launch, "ROOT": str(ROOT), "RUNDIR": rel(cp.parent),
           "STORE": f["store"], "NAME": f["name"], "SHA": f["sha256"], "URL": h["url"], "BIN": e["bin"], "FLAGS": e["flags"],
           "ENV": "".join(f"{k}={v} " for k, v in (e.get("env") or {}).items()), "PORT": h["url"].rsplit(":", 1)[1],
           "MINMEM": str(h.get("min_mem_avail_gib", 0)), "PAUSE": " ".join(h.get("pause", [])), "SSH": h.get("ssh", ""),
           "POWER": h.get("power", ""), "RBIN": e["bin"].replace("~", "\\$HOME", 1)}
    txt = HEAD + (LOCAL if h["kind"] == "local" else SSH) + "$PY $A audit $RC >> $LOG 2>&1\ncd $Q\n"
    for mode, m in rc["modes"].items():
        txt += MODE.replace("@MODE@", mode).replace("@ARM@", m["arm"]).replace("@ARGS@", shlex.join(run_argv(rc, path, mode)))
    txt += TAIL
    for k, v in sub.items(): txt = txt.replace(f"@{k}@", v)
    left = re.search(r"@[A-Z]+@", txt)
    if left: raise SystemExit(f"unfilled placeholder {left.group()}")
    if stdout: return print(txt)
    cp.parent.mkdir(parents=True, exist_ok=True); cp.write_text(txt); cp.chmod(0o755)
    print("wrote", rel(cp)); print("launch:", launch)


def compare(arm_a, arm_b, tol=1e-6):
    """Item-by-item reproduction check between two stored M1 arms (pipeline acceptance, engine conformance)."""
    load = lambda arm: {r["id"]: r for r in map(json.loads, open(QA / "raw" / f"main_{arm}.jsonl")) if "id" in r}
    A, B = load(arm_a), load(arm_b); ids = sorted(set(A) & set(B)); bad = {}
    for f in ("content", "finish", "grade"):
        bad[f] = [i for i in ids if A[i].get(f) != B[i].get(f)]
    bad["P_abs"] = [i for i in ids if (A[i]["P_abs"] is None) != (B[i]["P_abs"] is None) or
                    (A[i]["P_abs"] is not None and abs(A[i]["P_abs"] - B[i]["P_abs"]) > tol)]
    print(f"{arm_a} vs {arm_b}: {len(ids)} shared items ({len(A)} / {len(B)})")
    for f, v in bad.items(): print(f"  {f}: {len(v)} differ" + (f" (first: {', '.join(v[:5])})" if v else ""))
    return len(ids) == len(A) == len(B) and not any(bad.values())


def main():
    ap = argparse.ArgumentParser(); sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("check").add_argument("recipes", nargs="*")
    x = sp.add_parser("args"); x.add_argument("recipe"); x.add_argument("mode")
    x = sp.add_parser("prereg"); x.add_argument("recipe"); x.add_argument("--force", action="store_true"); x.add_argument("--stdout", action="store_true")
    sp.add_parser("guard").add_argument("recipe")
    x = sp.add_parser("chain"); x.add_argument("recipe"); x.add_argument("--stdout", action="store_true")
    x = sp.add_parser("smoke"); x.add_argument("recipe"); x.add_argument("mode")
    sp.add_parser("audit").add_argument("recipe")
    x = sp.add_parser("compare"); x.add_argument("arm_a"); x.add_argument("arm_b")
    a = ap.parse_args()
    if a.cmd == "check": return check(a.recipes or None)
    if a.cmd == "compare": sys.exit(0 if compare(a.arm_a, a.arm_b) else 1)
    p, rc = next(recipes([a.recipe]))
    if a.cmd == "guard": sys.exit(0 if guard(p, rc) else 1)
    if a.cmd == "prereg": return prereg(p, rc, a.force, a.stdout)
    if a.cmd == "chain": return chain(p, rc, a.stdout)
    if a.cmd == "smoke": sys.exit(0 if smoke(rc, a.mode) else 1)
    if a.cmd == "audit": return audit(rc)
    if not guard(p, rc, quiet=True): guard(p, rc); sys.exit(1)
    if not HOSTS[rc["host"]]["url"]: sys.exit(f"host {rc['host']} has no fixed test URL in hosts.json; set one for this run")
    print(shlex.join([str(QA / "run_main.py"), *run_argv(rc, p, a.mode)]))


if __name__ == "__main__":
    main()
