#!/usr/bin/env python3
"""General HumanEval+ harness for the Battle panel — supports temp-0 (k=1, deterministic) AND
creator-recommended-temp deployment runs (k>1 sampled). The k=1 path is logic-identical to
puzzle_humanevalplus.py / laguna_hep164.py so temp-0 and temp-rec numbers stay comparable per model.

At temp>0 a single pass is one sample from a distribution, so set HEP_K>=3 (5 preferred): the harness
fires K completions per problem and reports pass@1 as (a) pooled = passing_samples/(N*K) and
(b) per-sweep mean ± std across the K virtual sweeps (the interpretable run-to-run spread). Buckets
(PASS/WRONG/TRUNCATED/NO_ANSWER) tallied over all N*K samples; one representative failing trace saved
per problem (avoids N*K files). Reasoning model: extract from content THEN reasoning_content.

Env:
  HEP_MODEL   model label (for the json)                 default "unknown"
  HEP_ENDPOINT chat/completions URL                      default http://10.0.0.194:8091/v1/chat/completions
  HEP_TEMP    temperature                                default 0
  HEP_TOP_P   top_p (sent only if set)                   default unset
  HEP_TOP_K   top_k (sent only if set; llama-server ext) default unset
  HEP_K       completions per problem                    default 1
  HEP_MAXTOK  max_tokens                                 default 16000
  HEP_PREFIX  output file/dir prefix                     default "hep"
  HEP_TAG     run tag (namespaces outputs)               default f"t{temp}_k{K}"
Usage: hep_eval.py"""
import json, urllib.request, subprocess, tempfile, os, re, time, sys, gzip
from statistics import mean, pstdev
from concurrent.futures import ThreadPoolExecutor, as_completed

def degen_ratio(s):
    if not s: return 1.0
    b = s.encode("utf-8", "ignore")
    return len(gzip.compress(b, 6)) / max(len(b), 1)

ENDPOINT = os.environ.get("HEP_ENDPOINT", "http://10.0.0.194:8091/v1/chat/completions")
MODEL    = os.environ.get("HEP_MODEL", "unknown")
TEMP     = float(os.environ.get("HEP_TEMP", "0"))
TOP_P    = os.environ.get("HEP_TOP_P")  # str or None
TOP_K    = os.environ.get("HEP_TOP_K")
MIN_P    = os.environ.get("HEP_MIN_P")   # sent only if set (part of some cards' rec sampling)
PRES_PEN = os.environ.get("HEP_PRESENCE_PENALTY")  # some cards ship this high (e.g. 1.5) as anti-loop
FREQ_PEN = os.environ.get("HEP_FREQUENCY_PENALTY")
REP_PEN  = os.environ.get("HEP_REPEAT_PENALTY")
SYSTEM   = os.environ.get("HEP_SYSTEM")  # optional system prompt; unset => model's DEFAULT template system msg
TOOLS    = os.environ.get("HEP_TOOLS")   # optional JSON array of tool schemas (agent-pipeline condition)
_TOOLS   = json.loads(TOOLS) if TOOLS else None
THINK    = os.environ.get("HEP_THINK", "1")  # "0" -> disable model thinking via chat_template_kwargs enable_thinking:false
K        = int(os.environ.get("HEP_K", "1"))
MAXTOK   = int(os.environ.get("HEP_MAXTOK", "16000"))
PREFIX   = os.environ.get("HEP_PREFIX", "hep")
TAG      = os.environ.get("HEP_TAG", f"t{TEMP}_k{K}")
WORKERS  = 1  # single in-flight -> one server slot -> no batch-nondeterminism confound
EXEC_TO  = 60
HERE = os.path.dirname(os.path.abspath(__file__))

PREAMBLE = ("from typing import *\nimport math\nimport re\nimport collections\n"
            "from collections import *\nimport itertools\nfrom itertools import *\n"
            "import functools\nimport heapq\nimport bisect\nimport string\nimport numpy as np\n")

allp = {json.loads(l)["task_id"]: json.loads(l) for l in open(os.path.join(HERE, "humanevalplus.jsonl"))}
problems = [allp[t] for t in sorted(allp, key=lambda t: int(t.split("/")[1]))]
_only = os.environ.get("HEP_ONLY")   # optional comma-sep task_ids (e.g. re-run just the loopers)
if _only:
    _keep = set(_only.split(","))
    problems = [p for p in problems if p["task_id"] in _keep]
N = len(problems)


def preflight():
    """Prove the grader can pass a KNOWN-GOOD solution before spending any inference.

    Why this exists (2026-08-06): PREAMBLE ends with `import numpy as np`. On a host without numpy
    that import raises at the top of EVERY generated program, before a single test runs, so every
    problem scores WRONG and the run reports 0% pass@1.

    It fails SYMMETRICALLY, which is the dangerous part. A base-vs-variant comparison would have come
    back 0% vs 0% -- a clean null that would have CONFIRMED a pre-registered "the two arms differ by
    <=3pp" prediction. A missing dependency would have been reported as a scientific finding.

    Standard §1: an exit code is not evidence a measurement ran; find the measurement's own artifact.
    Guards abort, they do not warn.
    """
    probe = problems[0]
    canon = probe.get("canonical_solution")
    if not canon:
        print("[preflight] SKIP: no canonical_solution in dataset", file=sys.stderr)
        return
    program = (PREAMBLE + "\n" + probe["prompt"] + "\n" + canon + "\n\n"
               + probe["test"] + f"\n\ncheck({probe['entry_point']})\n")
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(program); path = f.name
    try:
        r = subprocess.run([sys.executable, path], capture_output=True, timeout=EXEC_TO, text=True)
    finally:
        os.unlink(path)
    if r.returncode != 0:
        tail = (r.stderr.strip().splitlines() or ["<no stderr>"])[-1]
        sys.exit(
            f"[preflight] FATAL: the grader cannot pass {probe['task_id']}'s own canonical solution.\n"
            f"  interpreter : {sys.executable}\n"
            f"  error       : {tail}\n"
            f"  Every problem would score WRONG and the run would report 0% pass@1 for any model.\n"
            f"  Fix the execution environment (PREAMBLE imports: typing, math, re, collections,\n"
            f"  itertools, functools, heapq, bisect, string, numpy) before measuring anything."
        )
    print(f"[preflight] OK: grader passes {probe['task_id']} canonical solution "
          f"({sys.executable})", file=sys.stderr)


preflight()


def query(text):
    _msgs = ([{"role":"system","content":SYSTEM}] if SYSTEM else []) + [{"role":"user","content":text}]
    payload = {"messages":_msgs, "temperature":TEMP, "max_tokens":MAXTOK}
    if _TOOLS: payload["tools"] = _TOOLS
    if TOP_P is not None: payload["top_p"] = float(TOP_P)
    if TOP_K is not None: payload["top_k"] = int(TOP_K)
    if MIN_P is not None: payload["min_p"] = float(MIN_P)
    if PRES_PEN is not None: payload["presence_penalty"] = float(PRES_PEN)
    if FREQ_PEN is not None: payload["frequency_penalty"] = float(FREQ_PEN)
    if REP_PEN  is not None: payload["repeat_penalty"] = float(REP_PEN)
    if THINK == "0": payload["chat_template_kwargs"] = {"enable_thinking": False}
    req = urllib.request.Request(ENDPOINT, data=json.dumps(payload).encode(),
                                 headers={"Content-Type":"application/json"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=2400) as r:
                d = json.loads(r.read())
            ch = d["choices"][0]
            return (ch["message"].get("content") or "", ch["message"].get("reasoning_content") or "",
                    ch.get("finish_reason"), d.get("usage", {}))
        except Exception as e:
            if attempt == 2: return f"__ERR__ {e}", "", "error", {}
            time.sleep(5)

def last_block(s):
    blocks = re.findall(r"```(?:python)?\s*\n(.*?)```", s, re.S)
    return blocks[-1] if blocks else None

def one_sample(p):
    """One completion -> (bucket, passed, meta). Identical logic to the temp-0 harnesses."""
    instr = ("Complete this Python function. Return ONLY the complete function "
             "in a ```python code block.\n\n" + p["prompt"])
    content, rc, finish, usage = query(instr)
    code, src = last_block(content), "content"
    if code is None:
        code, src = last_block(rc), "reasoning"
    if code is None:
        code, src = "", "none"
    program = PREAMBLE + "\n" + p["prompt"] + "\n\n" + code + "\n\n" + p["test"] + f"\n\ncheck({p['entry_point']})\n"
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(program); path = f.name
    err = ""
    try:
        r = subprocess.run([sys.executable, path], capture_output=True, timeout=EXEC_TO, text=True)
        passed = (r.returncode == 0)
        if not passed:
            err = (r.stderr.strip().splitlines() or ["nonzero"])[-1]
    except subprocess.TimeoutExpired:
        passed, err = False, "EXEC_TIMEOUT"
    finally:
        os.unlink(path)
    if src == "none":
        # finish=tool_calls => the model answered WITH A TOOL CALL (content is empty by design).
        # Scoring that as NO_ANSWER conflates "chose to call a tool" with "produced nothing".
        if finish == "tool_calls":   bucket = "TOOL_CALL"
        elif finish == "length":     bucket = "TRUNCATED"
        else:                        bucket = "NO_ANSWER"
    elif passed:
        bucket = "PASS"
    elif err == "EXEC_TIMEOUT":
        bucket = "EXEC_TIMEOUT"
    else:
        bucket = "WRONG"
    return {"bucket": bucket, "passed": passed, "finish": finish, "src": src, "err": err[:90],
            "out_tok": usage.get("completion_tokens"), "content": content, "rc": rc}

def run_one(p):
    samples = [one_sample(p) for _ in range(K)]          # K completions (K=1 => same as temp-0 harness)
    passes = [s["passed"] for s in samples]
    pass_frac = sum(passes) / K
    # save ONE representative failing trace per problem (first non-PASS), tagged with pass_frac
    fail = next((s for s in samples if not s["passed"]), None)
    if fail is not None:
        d = os.path.join(HERE, f"{PREFIX}_traces_{TAG}")
        os.makedirs(d, exist_ok=True)
        gr = degen_ratio(fail["rc"])
        with open(os.path.join(d, p["task_id"].replace("/", "_") + f".{fail['bucket']}.txt"), "w") as tf:
            tf.write(f"### {p['task_id']}  pass_frac={pass_frac:.2f} (of K={K})  first-fail bucket={fail['bucket']} "
                     f"finish={fail['finish']} gzip_ratio={gr:.3f} code_src={fail['src']}\n")
            tf.write(f"### PROMPT:\n{p['prompt']}\n### CONTENT:\n{fail['content']}\n### REASONING_CONTENT:\n{fail['rc']}\n")
    return {"task_id": p["task_id"], "pass_frac": pass_frac, "passes": passes,
            "buckets": [s["bucket"] for s in samples], "finishes": [s["finish"] for s in samples],
            "srcs": [s["src"] for s in samples], "out_toks": [s["out_tok"] for s in samples],
            "rc_chars": [len(s["rc"]) for s in samples]}   # reasoning_content length -> did thinking fire?

results, t0 = [], time.time()
with ThreadPoolExecutor(WORKERS) as ex:
    futs = {ex.submit(run_one, p): p for p in problems}
    done = 0
    for fut in as_completed(futs):
        r = fut.result(); results.append(r); done += 1
        print(f"[{done:3d}/{N}] {r['task_id']:14s} pass_frac={r['pass_frac']:.2f}  "
              f"buckets={','.join(b[0] for b in r['buckets'])}  toks={r['out_toks']}", flush=True)

results.sort(key=lambda r: int(r["task_id"].split("/")[1]))
from collections import Counter
sample_tally = Counter(b for r in results for b in r["buckets"])   # over all N*K samples
pooled_pass = sum(sum(r["passes"]) for r in results)               # exact int: total passing samples
pooled_rate = pooled_pass / (N * K)
sweep_rates = [sum(1 for r in results if r["passes"][j]) / N for j in range(K)]  # rate of j-th sample across problems
fully   = sum(1 for r in results if r["pass_frac"] == 1.0)
never   = sum(1 for r in results if r["pass_frac"] == 0.0)
flaky   = N - fully - never
el = time.time() - t0
print(f"\n=== {MODEL} HumanEval+ FULL {N} | temp {TEMP} top_p {TOP_P} top_k {TOP_K} min_p {MIN_P} | thinking {'OFF' if THINK=='0' else 'ON'} | K={K} | tag {TAG} ===")
print(f"sample buckets (of {N*K}): " + " ".join(f"{b}={sample_tally.get(b,0)}"
      for b in ["PASS","WRONG","TRUNCATED","TOOL_CALL","NO_ANSWER","EXEC_TIMEOUT"]))
if K == 1:
    print(f"RAW pass@1 = {int(pooled_pass)}/{N} = {pooled_rate*100:.1f}%   (NOT final — hand-adjudicate traces)")
else:
    print(f"pass@1 POOLED = {pooled_rate*100:.2f}%  ({int(pooled_pass)}/{N*K} samples)")
    print(f"pass@1 per-sweep = {mean(sweep_rates)*100:.2f}% ± {pstdev(sweep_rates)*100:.2f}%  "
          f"(K={K} virtual sweeps; min {min(sweep_rates)*100:.1f}% max {max(sweep_rates)*100:.1f}%)")
    print(f"consistency: {fully}/{N} solved every time | {never}/{N} never | {flaky}/{N} FLAKY (sampling-sensitive)")
_rc = [c for r in results for c in r.get("rc_chars",[])]
if _rc:
    _fired = sum(1 for c in _rc if c > 0)
    print(f"THINKING FIRED on {_fired}/{len(_rc)} samples ({100*_fired/len(_rc):.1f}%) | "
          f"mean reasoning_content = {sum(_rc)/len(_rc):.0f} chars | "
          f"system_prompt={'PERSONA' if SYSTEM else 'default'} | tools={'YES' if _TOOLS else 'no'}")
print(f"elapsed {el:.0f}s")
json.dump({"model":MODEL,"bench":"HumanEval+ full","temp":TEMP,"top_p":TOP_P,"top_k":TOP_K,"min_p":MIN_P,
           "presence_penalty":PRES_PEN,"frequency_penalty":FREQ_PEN,"repeat_penalty":REP_PEN,
           "system_prompt":bool(SYSTEM),"tools":bool(_TOOLS),"enable_thinking":(THINK!="0"),"K":K,"tag":TAG,
           "endpoint":ENDPOINT,"N":N,"pooled_pass@1":pooled_rate,
           "sweep_rates":sweep_rates,"sweep_mean":mean(sweep_rates),"sweep_std":pstdev(sweep_rates),
           "consistency":{"fully":fully,"never":never,"flaky":flaky},
           "sample_tally":dict(sample_tally),"elapsed_s":el,"results":results},
          open(os.path.join(HERE, f"{PREFIX}_results_{TAG}.json"), "w"), indent=2)
print(f"=== SIGNAL: {PREFIX} {TAG} done (pooled {pooled_rate*100:.1f}%) ===")
