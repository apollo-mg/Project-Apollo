#!/usr/bin/env python3
"""PREREG_CROSS_MODEL.md: feed Bonsai's exact token sequences to .73's Qwen3.8 Q6_K and read the next-token
distribution at Bonsai's wrap-up points and real END points. Gate S: .73's token ids must equal Bonsai's at every
probe position. Output raw/xmodel_q6k.jsonl (one row per point) + a printed table."""
import glob, json, math, os
from pathlib import Path
import httpx

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
N73 = "http://10.0.0.73:8080"
THINK_END = 248069


def main():
    c = httpx.Client(timeout=900)
    props = c.get(f"{N73}/props").json()
    fx = json.load(open(ROOT / "data/receipts/viability/fixture_v0_beta.json"))["tier_cal"]
    qs = {i["id"]: i["q"] for i in fx["items"]}
    rows = {}
    for d in ("out_bonsai1", "out_bonsai2"):
        for f in glob.glob(str(ROOT / f"data/receipts/marker-penalty/raw/{d}/armA_rep*.jsonl")):
            rep = f.split("_rep")[1][0]
            for l in open(f):
                r = json.loads(l); rows[(r["id"], rep)] = r
    W = json.load(open(HERE / "EXPLORE_wrapup.json"))
    out = open(HERE / "raw/xmodel_q6k.jsonl", "w")
    out.write(json.dumps({"meta": {"model_path": props.get("model_path", "").split("/")[-1],
                                   "build": props.get("build_info"), "slots": props.get("total_slots")}}) + "\n")
    for name, d in W.items():
        L = [json.loads(l) for l in open(HERE / f"raw/full_{name}.jsonl")]
        m = L[0]["meta"]; B = {r["trace_pos"]: r for r in L[1:]}
        P = c.post(f"{N73}/apply-template", json={"messages": [{"role": "user", "content": fx["prompt"].format(q=qs[m["id"]])}],
                                                  "chat_template_kwargs": {"reasoning_effort": "xhigh"}}).json()["prompt"]
        tp = c.post(f"{N73}/tokenize", json={"content": P}).json()["tokens"]
        ids = c.post(f"{N73}/tokenize", json={"content": P + rows[(m["id"], m["rep"])]["reasoning"]}).json()["tokens"]
        mism = sum(1 for r in L[1:] if not r["end"] and ids[r["pos"]] != r["next_id"])
        gate = len(tp) == m["n_prompt"] and len(ids) == m["n_total"] and mism == 0
        print(f"{name}: gate S {'PASS' if gate else 'FAIL'} (n_prompt {len(tp)}/{m['n_prompt']}, total {len(ids)}/{m['n_total']}, mismatches {mism})", flush=True)
        if not gate:
            out.write(json.dumps({"trace": name, "gate_S": False}) + "\n"); continue
        points = [(h["trace_pos"], "wrapup", h) for h in d["wrapups"] if h["next"] != "END"]
        if m["status"] != "NO-STOP/REC" and d["wrapups"]:
            endr = next(r for r in L[1:] if r["end"])
            points.append((endr["trace_pos"], "END", None))
        for tpos, kind, h in points:
            br = B[tpos]
            r = c.post(f"{N73}/completion", json={"prompt": ids[:br["pos"]], "n_predict": 1, "n_probs": 20, "temperature": 0,
                                                  "cache_prompt": False, "post_sampling_probs": False}).json()
            cp = r["completion_probabilities"][0]
            top = [(t["id"], t["token"], t["logprob"]) for t in cp["top_logprobs"]]
            pq = sum(math.exp(t[2]) for t in top if t[0] == THINK_END)
            pb = sum(math.exp(t[2]) for t in br["top"] if t[0] == THINK_END)
            rec = {"trace": name, "status": m["status"], "trace_pos": tpos, "kind": kind,
                   "line": h["line"] if h else None, "bonsai_next": h["next"] if h else "END",
                   "q6k_p_think_end": pq, "bonsai_p_think_end": pb,
                   "q6k_top5": [(t[1], round(math.exp(t[2]), 3)) for t in top[:5]],
                   "bonsai_top5": [(t[1], round(math.exp(t[2]), 3)) for t in br["top"][:5]],
                   "prompt_n": r["timings"]["prompt_n"]}
            out.write(json.dumps(rec) + "\n"); out.flush(); os.fsync(out.fileno())
            print(f"  @{tpos:5d} {kind:6s} P(</think>) Q6_K {pq:.3f} vs Bonsai {pb:.3f} | Q6_K {rec['q6k_top5'][:3]} | Bonsai {rec['bonsai_top5'][:3]}", flush=True)


if __name__ == "__main__":
    main()
