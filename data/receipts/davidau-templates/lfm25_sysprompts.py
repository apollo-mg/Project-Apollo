#!/usr/bin/env python3
"""PREREG_LFM25_SYSPROMPTS.md driver: the same LFM2.5-2.6B (TRIM template, mode `off`) with four system prompts on the
16 CAL items x 3 seeds: NONE, XHIGH (Qwen3.8's xhigh text, verbatim), OMNI (DavidAU's omni text), OMNID2 (omni minus
its "DIMENSION 2" block). Only the system text differs. Texts are read from sysprompts_raw.json (local; DavidAU's text
is "all rights reserved", so only sha256 prefixes are committed) and checked against the registered hashes. Sampling,
grader and row format as lfm25_modes.py. One discarded warm-up. Rows flush+fsync, resumable.
Usage: lfm25_sysprompts.py [--url http://127.0.0.1:8096] [--texts PATH] [--out lfm25_sysprompts/rows.jsonl]"""
import argparse, hashlib, json, os, sys, time, urllib.request
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "viability"))
from run_fixture_structfix import classify, pick_answer  # noqa: E402
FIX = json.load(open(HERE.parent / "viability" / "fixture_v0_beta.json"))["tier_cal"]
SAMPLING = {"temperature": 1.0, "top_k": 64, "min_p": 0.05, "top_p": 0.95, "repeat_penalty": 1.0}
SEEDS = [1001, 1002, 1003]
REG = {"XHIGH": ("xhigh", "982cfb432c323e6d"), "OMNI": ("omni", "c7995a73c16f94f2"), "OMNID2": ("omni_noD2", "29b7d220c2242c0c")}
def post(u, p, b, t=1800):
    return json.load(urllib.request.urlopen(urllib.request.Request(u + p, json.dumps(b).encode(), {"content-type": "application/json"}), timeout=t))
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8096")
    ap.add_argument("--texts", default="/mnt/TG_2TB/AI/Models/davidau-lfm25/sysprompts_raw.json")
    ap.add_argument("--out", default=str(HERE / "lfm25_sysprompts" / "rows.jsonl"))
    a = ap.parse_args()
    T = json.load(open(a.texts)); SYS = {"NONE": None}
    for arm, (k, h) in REG.items():
        assert hashlib.sha256(T[k].encode()).hexdigest().startswith(h), f"text {k} does not match its registered hash"
        SYS[arm] = T[k]
    for arm, s in SYS.items():   # gate: the render carries exactly this system text and no mode injection
        msgs = ([{"role": "system", "content": s}] if s else []) + [{"role": "user", "content": "{REASON:off} Q"}]
        p = post(a.url, "/apply-template", {"messages": msgs, "chat_template_kwargs": {"enable_thinking": True}})["prompt"]
        assert p.count("<|im_start|>system") == (1 if s else 0) and (s is None or s in p), f"gate: {arm} render wrong"
    print("gate passed", flush=True)
    post(a.url, "/v1/chat/completions", {"messages": [{"role": "user", "content": "{REASON:off} Say ready."}], "max_tokens": 16,
                                          "cache_prompt": False})                      # discarded warm-up
    out = Path(a.out); out.parent.mkdir(parents=True, exist_ok=True)
    done = {(r["arm_sys"], r["seed"], r["id"]) for r in map(json.loads, open(out))} if out.exists() else set()
    with open(out, "a") as f:
        for seed in SEEDS:
            for it in FIX["items"]:
                for arm, s in SYS.items():
                    if (arm, seed, it["id"]) in done:
                        continue
                    msgs = ([{"role": "system", "content": s}] if s else []) + \
                           [{"role": "user", "content": "{REASON:off} " + FIX["prompt"].format(q=it["q"])}]
                    t0 = time.time()
                    try:
                        r = post(a.url, "/v1/chat/completions", {"messages": msgs, "max_tokens": 16000, "cache_prompt": False,
                                                                  "seed": seed, **SAMPLING})
                        ch = r["choices"][0]; m = ch["message"]; fin = ch.get("finish_reason")
                        got, nm = pick_answer(m.get("content") or "", m.get("reasoning_content") or "", fin)
                        row = {"arm_sys": arm, "seed": seed, "id": it["id"], "arm": it["arm"], "gold": it["gold"], "finish": fin,
                               "got": got, "n_matches": nm, "grade": classify(got, it["gold"]) if fin != "length" else "NO-STOP",
                               "completion_tokens": r["usage"]["completion_tokens"], "prompt_tokens": r["usage"]["prompt_tokens"],
                               "reasoning_chars": len(m.get("reasoning_content") or ""), "content": (m.get("content") or "")[-2000:],
                               "secs": round(time.time() - t0, 1)}
                    except Exception as e:                                       # noqa: BLE001
                        row = {"arm_sys": arm, "seed": seed, "id": it["id"], "arm": it["arm"], "grade": "ERROR", "error": str(e)[:300]}
                    f.write(json.dumps(row, ensure_ascii=False) + "\n"); f.flush(); os.fsync(f.fileno())
                    print(f"{arm:7s} s{seed} {it['id']:7s} {row['grade']:16s} {row.get('completion_tokens', '-'):>6}", flush=True)
    print("ALL_DONE", flush=True)
if __name__ == "__main__":
    main()
