#!/usr/bin/env python3
"""Driver and scorer for PREREG_EXL3_RDNA4_MTP.md (EXL3 campaign, test 9). Runs on the control plane.

Depth needs a server restart per point (per-request speculative.n_max is ignored under draft-mtp), which
is cheap here: loads are ~13 s on the 9070. Every row is appended, flushed and fsynced.

Usage:  exl3_rdna4_mtp.py depths | bench | score
"""
import json, os, re, signal, statistics, subprocess, sys, time, urllib.request

BUILD = "/mnt/TG_2TB/Projects/buun-da458/build_rocm"
BIN = f"{BUILD}/bin"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rdna4_mtp")
RES = os.path.join(OUT, "results.jsonl")
PORT = 8195
H = f"http://127.0.0.1:{PORT}"
M = "/mnt/TG_2TB/AI/Models"
ARMS = [   # (label, path, pair)
    ("E3",  f"{M}/exl3/Qwen3.8-27B-exl3-3.00bpw", "A"),
    ("G3x", f"{M}/gsq-rco/Qwen3.8-27B-GSQ-RCO-IQ3_XXS-mtp.gguf", "A"),
    ("E35", f"{M}/exl3/Qwen3.8-27B-exl3-3.50bpw", "B"),
    ("G3m", f"{M}/pelican3/Qwen3.8-27B.i1-IQ3_M.gguf", "B"),
]
DEPTHS = [0, 1, 2, 3]
BASE_FLAGS = ["-ngl", "99", "-c", "8192", "-ctk", "q8_0", "-ctv", "q8_0", "-fa", "on", "-np", "1", "--jinja"]
SPEED = "Write a detailed explanation of how a hash table works."
FACT = "What is the capital of France? Answer with one word."
BENCH_ARGS = ["-p", "64", "-n", "8", "-ub", "1,2,4,8,16,1", "-r", "3", "-o", "json", "-ngl", "99",
              "-fa", "on", "-ctk", "q8_0", "-ctv", "q8_0"]


def log(msg):
    line = f"{time.strftime('%F %T')} {msg}"
    print(line, flush=True)
    with open(os.path.join(OUT, "rdna4_mtp.log"), "a") as f:
        f.write(line + "\n")


def emit(row):
    row["ts"] = time.strftime("%F %T")
    with open(RES, "a") as f:
        f.write(json.dumps(row) + "\n")
        f.flush()
        os.fsync(f.fileno())


def req(path, body, timeout=600):
    r = urllib.request.Request(H + path, data=json.dumps(body).encode(),
                               headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=timeout) as resp:
        return json.loads(resp.read())


def flags(k):
    return BASE_FLAGS + (["--spec-type", "draft-mtp", "--draft-max", str(k)] if k > 0 else [])


def start(label, model, k):
    logf = open(os.path.join(OUT, f"server_{label}_d{k}.log"), "w")
    p = subprocess.Popen([f"{BIN}/llama-server", "-m", model, *flags(k), "--host", "127.0.0.1",
                          "--port", str(PORT)], stdout=logf, stderr=subprocess.STDOUT,
                         start_new_session=True)
    t0 = time.time()
    while time.time() - t0 < 600:
        if p.poll() is not None:
            return p, None, f"server exited rc={p.returncode}"
        try:
            if "choices" in req("/v1/chat/completions",
                                {"messages": [{"role": "user", "content": "Say READY"}], "max_tokens": 4},
                                timeout=45):
                return p, time.time() - t0, None
        except Exception:
            pass
        time.sleep(3)
    return p, None, "never answered within 600 s"


def stop(p):
    if p.poll() is None:
        os.killpg(p.pid, signal.SIGTERM)
        try:
            p.wait(30)
        except subprocess.TimeoutExpired:
            os.killpg(p.pid, signal.SIGKILL)
            p.wait()
    time.sleep(2)


def run_point(label, model, pair, k):
    base = {"arm": label, "pair": pair, "model": model, "depth": k}
    p, load_s, err = start(label, model, k)
    if err:
        emit({**base, "stage": "load", "ok": False, "error": err})
        log(f"  {label} d{k} LOAD FAILED: {err}")
        stop(p)
        return
    emit({**base, "stage": "load", "ok": True, "load_s": round(load_s, 1)})
    try:
        if k == 0:
            r = req("/v1/chat/completions", {"messages": [{"role": "user", "content": FACT}],
                    "max_tokens": 64, "temperature": 0, "chat_template_kwargs": {"enable_thinking": False}})
            emit({**base, "stage": "fact", "content": r["choices"][0]["message"].get("content")})
        for rep in (1, 2, 3):
            t = req("/completion", {"prompt": SPEED, "n_predict": 128, "temperature": 0, "top_k": 1,
                                    "cache_prompt": False, "ignore_eos": True}).get("timings", {})
            emit({**base, "stage": "depth", "rep": rep, "timings": t})
        log(f"  {label} d{k}: {t.get('predicted_per_second', 0):.2f} t/s  draft {t.get('draft_n_accepted')}/{t.get('draft_n')}")
    except Exception as e:
        emit({**base, "stage": "error", "error": repr(e)})
        log(f"  {label} d{k} STAGE FAILED: {e!r}")
    finally:
        stop(p)


def run_bench(label, model):
    log(f"=== llama-bench {label}")
    p = subprocess.run([f"{BIN}/llama-bench", "-m", model, *BENCH_ARGS], capture_output=True,
                       text=True, timeout=3600)
    with open(os.path.join(OUT, f"bench_{label}.json"), "w") as f:
        f.write(p.stdout)
    try:
        for e in json.loads(p.stdout):
            emit({"arm": label, "stage": "bench", "n_prompt": e.get("n_prompt"), "n_gen": e.get("n_gen"),
                  "n_ubatch": e.get("n_ubatch"), "avg_ts": e.get("avg_ts"), "stddev_ts": e.get("stddev_ts"),
                  "build_commit": e.get("build_commit")})
        log(f"  {label}: {len(json.loads(p.stdout))} rows")
    except Exception as e:
        emit({"arm": label, "stage": "error", "rc": p.returncode, "error": repr(e), "stderr": p.stderr[-600:]})
        log(f"  {label} bench FAILED: {e!r}")


def score():
    rows = [json.loads(l) for l in open(RES) if l.strip()]

    def at(arm, k):
        return [r for r in rows if r.get("arm") == arm and r.get("stage") == "depth" and r.get("depth") == k]

    def t(r, key):
        return (r.get("timings") or {}).get(key)

    def dec(arm, k):
        v = [x for x in (t(r, "predicted_per_second") for r in at(arm, k)) if x]
        return statistics.median(v) if v else None

    def dpt(arm, k):
        rs = at(arm, k)
        d = sum(int(t(r, "draft_n") or 0) for r in rs)
        n = sum(int(t(r, "predicted_n") or 0) for r in rs)
        return d / n if n else None

    def gain(arm, k):
        d0, dk = dec(arm, 0), dec(arm, k)
        return dk / d0 if d0 and dk else None

    def best(arm):
        c = [(dec(arm, k), k) for k in DEPTHS if dec(arm, k)]
        return max(c)[1] if c else None

    def fmt(x, s=".2f"):
        return "-" if x is None else format(x, s)

    def verdict(b):
        return "CONFIRMED" if b else "FALSIFIED"

    print("| arm | pair | " + " | ".join(f"d{k}" for k in DEPTHS) + " | best | gain | drafted/token at best |")
    print("|---" * (5 + len(DEPTHS)) + "|")
    for label, _, pair in ARMS:
        b = best(label)
        print(f"| {label} | {pair} | " + " | ".join(fmt(dec(label, k)) for k in DEPTHS) +
              f" | {b if b is not None else '-'} | {fmt(gain(label, b) if b else None)} | {fmt(dpt(label, b) if b else None)} |")

    print("\n## Predictions\n")
    gates = []
    for label, _, _ in ARMS:
        d0, d3 = dpt(label, 1), dpt(label, 3)
        gates.append(bool(d0 is not None and d3 is not None and d3 > d0))
    print(f"- **P-N1** (gate): {verdict(all(gates))} (drafted/token rises with depth in " +
          ", ".join(f"{a[0]}:{'yes' if g else 'NO'}" for a, g in zip(ARMS, gates)) + ")")
    print(f"- **P-N2**: " + verdict(all((gain(a[0], best(a[0])) or 0) > 1.0 for a in ARMS)) +
          " (" + ", ".join(f"{a[0]} {fmt(gain(a[0], best(a[0])))}" for a in ARMS) + ")")
    for pair, e, g in (("A", "E3", "G3x"), ("B", "E35", "G3m")):
        ge, gg = gain(e, best(e)), gain(g, best(g))
        de, dg = dec(e, best(e)), dec(g, best(g))
        print(f"- **P-N3/{pair}**: " + ("NOT TESTABLE" if None in (ge, gg) else
              f"{verdict(ge < gg)} (EXL3 {ge:.2f}x vs GGUF {gg:.2f}x)"))
        print(f"- **P-N4/{pair}**: " + ("NOT TESTABLE" if None in (best(e), best(g)) else
              f"{verdict(best(e) <= best(g))} (best depth {best(e)} vs {best(g)})"))
        print(f"- **P-N5/{pair}**: " + ("NOT TESTABLE" if None in (de, dg) else
              f"{verdict(de < dg)} ({de:.2f} vs {dg:.2f} t/s)"))
        if None not in (de, dg):
            ratio = de / dg
            print(f"- **P-N6/{pair}**: {verdict(abs(ratio - 0.648) <= 0.15)} (ratio {ratio:.3f} vs Pascal's 0.648)")

    pp = {}
    for r in rows:
        if r.get("stage") == "bench" and r.get("n_prompt"):
            pp.setdefault(r["arm"], {}).setdefault(r["n_ubatch"], []).append(r["avg_ts"])
    if pp:
        print("\n## The micro-batch curve on RDNA4\n")
        A = {}
        for arm, d in pp.items():
            base1 = max(d.get(1, [0]))
            A[arm] = {u: (max(v) if u == 1 else v[0]) / base1 for u, v in d.items() if base1}
            print(f"- **{arm}**: " + ", ".join(f"A({u})={A[arm][u]:.2f}" for u in sorted(A[arm])))
        if "E3" in A and "G3x" in A and 4 in A["E3"] and 4 in A["G3x"]:
            print(f"- **P-N7**: {verdict(A['E3'][4] < A['G3x'][4])} "
                  f"(A_EXL3(4)={A['E3'][4]:.2f} vs A_GGUF(4)={A['G3x'][4]:.2f}; Pascal was 1.92 vs 2.92)")


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    what = sys.argv[1] if len(sys.argv) > 1 else ""
    if what == "depths":
        for label, model, pair in ARMS:
            if not os.path.exists(model):
                log(f"SKIP {label}: {model} missing")
                continue
            log(f"=== {label} ({pair}) {os.path.basename(model)}")
            for k in DEPTHS:
                run_point(label, model, pair, k)
    elif what == "bench":
        for label, model, pair in ARMS:
            if pair == "A" and os.path.exists(model):
                run_bench(label, model)
    elif what == "score":
        score()
    else:
        sys.exit(__doc__)
