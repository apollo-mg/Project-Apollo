#!/usr/bin/env python3
"""Runner for PREREG_EINSTEIN_TERMINATION.md — does {REASON:einstein} terminate?

Three arms against one server: xhigh (control), einstein, einstein + a server-side thinking cap.
Non-termination is finish_reason == "length" at n_predict 8192.

Every row is appended, flushed and fsynced before the next request starts, and the runner skips
(arm, rep, item) cells already present, so a kill costs only the in-flight generation.

Usage:
  run_einstein.py --out einstein --arm A --rep 1 --item E-C1
  run_einstein.py --out einstein --all
"""
import argparse, json, os, sys, time
import urllib.request

HOST = os.environ.get("EIN_HOST", "http://127.0.0.1:8097")
N_PREDICT = 8192

ITEMS = {
    "E-C1": "Write a Python function that parses a duration string like '1h30m' or '45s' into a "
            "number of seconds. Handle the reasonable edge cases. Give me the function.",
    "E-C2": "Write a small Python command-line tool that removes duplicate lines from a file while "
            "preserving the original order, with an --ignore-case flag. Give me the script.",
    "E-I1": "Give me exactly three names for a home lab that benchmarks quantized language models "
            "on old datacenter GPUs. Three names, nothing else.",
    "E-I2": "Describe exactly two approaches to detecting when a language model is overthinking a "
            "problem. One paragraph each, two approaches total.",
}

# arm -> (reasoning_effort, reasoning_budget_tokens or None)
ARMS = {"A": ("xhigh", None), "B": ("einstein", None), "C": ("einstein", 1024)}


def already(path, arm, rep, item):
    if not os.path.exists(path):
        return False
    with open(path) as fh:
        for line in fh:
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if r.get("arm") == arm and r.get("rep") == rep and r.get("id") == item:
                return True
    return False


def generate(effort, budget, prompt, seed):
    body = {
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": N_PREDICT,
        "seed": seed,
        "temperature": 1.0,
        "top_p": 0.95,
        "top_k": 20,
        "min_p": 0.0,
        "chat_template_kwargs": {"reasoning_effort": effort},
    }
    if budget is not None:
        body["reasoning_budget_tokens"] = budget
    req = urllib.request.Request(
        HOST + "/v1/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=3600) as resp:
        d = json.loads(resp.read())
    ch = d["choices"][0]
    msg = ch["message"]
    return {
        "finish": ch.get("finish_reason"),
        "content": msg.get("content") or "",
        "reasoning": msg.get("reasoning_content") or msg.get("reasoning") or "",
        "prompt_tokens": d.get("usage", {}).get("prompt_tokens"),
        "completion_tokens": d.get("usage", {}).get("completion_tokens"),
        "wall_s": round(time.time() - t0, 2),
    }


def server_config():
    """The server's LIVE context and KV bits-per-value, read from /slots before each generation.

    The first version of this runner hardcoded n_ctx = 16384, and so recorded 16384 for pilot rows
    served at 12288 -- the exact failure mode (a config field written from assumption rather than
    measurement) that invalidated the CAL baseline comparison. Recording what the server reports
    makes that impossible. None means the read failed, and says so, rather than inventing a value.
    """
    try:
        with urllib.request.urlopen(HOST + "/slots", timeout=10) as resp:
            s = json.loads(resp.read())[0]
        return s.get("n_ctx"), s.get("kv_bpv")
    except Exception:
        return None, None


def run_cell(out, arm, rep, item):
    path = os.path.join(out, f"arm{arm}_rep{rep}.jsonl")
    os.makedirs(out, exist_ok=True)
    if already(path, arm, rep, item):
        print(f"  skip {arm}/{rep}/{item} (already recorded)")
        return
    effort, budget = ARMS[arm]
    seed = 2000 + rep
    n_ctx, kv_bpv = server_config()
    r = generate(effort, budget, ITEMS[item], seed)
    row = {
        "id": item, "arm": arm, "rep": rep, "seed": seed,
        "effort": effort, "budget_tokens": budget,
        "n_predict": N_PREDICT, "n_ctx": n_ctx, "kv_bpv": kv_bpv, "host": HOST,
        "model": os.environ.get("EIN_MODEL", "unset"),
        "prompt": ITEMS[item],
        **r,
    }
    # non-termination is the registered outcome; compute it here so scoring cannot drift
    row["nonterminating"] = (r["finish"] == "length")
    with open(path, "a") as fh:
        fh.write(json.dumps(row) + "\n")
        fh.flush()
        os.fsync(fh.fileno())
    print(f"  {arm}/{rep}/{item}: finish={r['finish']:8s} tok={r['completion_tokens']:6d} "
          f"think={len(r['reasoning']):6d}ch ans={len(r['content']):5d}ch {r['wall_s']:7.1f}s"
          + ("   <-- NON-TERMINATING" if row["nonterminating"] else ""))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--arm")
    ap.add_argument("--rep", type=int)
    ap.add_argument("--item")
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args()
    if a.all:
        # rotate arm order per (rep, item) so no arm owns a time slot
        for rep in (1, 2, 3):
            for i, item in enumerate(ITEMS):
                order = [["A", "B", "C"], ["B", "C", "A"], ["C", "A", "B"]][(i + rep) % 3]
                for arm in order:
                    run_cell(a.out, arm, rep, item)
    else:
        run_cell(a.out, a.arm, a.rep, a.item)
    return 0


if __name__ == "__main__":
    sys.exit(main())
