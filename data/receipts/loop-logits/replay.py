#!/usr/bin/env python3
"""PREREG_LOOP_LOGITS.md: teacher-forced replay of stored Bonsai traces, one probe per newline boundary.

Each probe: /completion with the prefix, n_predict 1, n_probs 20, and the TRUE next token forced by logit_bias +100,
so the slot cache only ever extends (a hybrid recurrent model cannot roll back). The server reports the RAW
distribution (checked: a forced token shows logprob -20.1 while the model's own top choice is 0.978).
Every 25th probe is re-sent with cache_prompt false (full prefill) for the validity gate V.
Output: raw/replay_<set>_<id>_rep<r>.jsonl, one row per probe, fsync'd.
"""
import argparse, glob, json, os, sys, time
from pathlib import Path
import httpx

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
U = "http://127.0.0.1:8231"
THINK_END = 248069
SETS = {"LOOP": [("CAL-U2", "3"), ("CAL-U5", "2"), ("CAL-U5", "3")],
        "LONG-OK": [("CAL-U2", "2"), ("CAL-U4", "2")]}


def load_rows():
    rows = {}
    for d in ("out_bonsai1", "out_bonsai2"):
        for f in glob.glob(str(ROOT / f"data/receipts/marker-penalty/raw/{d}/armA_rep*.jsonl")):
            rep = f.split("_rep")[1][0]
            for l in open(f):
                r = json.loads(l)
                rows[(r["id"], rep)] = r
    return rows


def probe(c, prefix, forced, cache=True):
    r = c.post(f"{U}/completion", json={"prompt": prefix, "n_predict": 1, "n_probs": 20, "temperature": 0,
                                         "cache_prompt": cache, "logit_bias": [[forced, 100]],
                                         "post_sampling_probs": False})
    r.raise_for_status()
    j = r.json()
    cp = j["completion_probabilities"][0]
    assert cp["id"] == forced, (cp["id"], forced)
    top = [(t["id"], t["token"], t["logprob"]) for t in cp["top_logprobs"]]
    return {"true_lp": cp["logprob"], "top": top, "prompt_n": j["timings"]["prompt_n"]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sets", default="LONG-OK,LOOP,SHORT")
    ap.add_argument("--full", action="store_true", help="Deviation 1: every probe is a full prefill (cache_prompt false)")
    a = ap.parse_args()
    c = httpx.Client(timeout=900)
    fx = json.load(open(ROOT / "data/receipts/viability/fixture_v0_beta.json"))["tier_cal"]
    qs = {i["id"]: i["q"] for i in fx["items"]}
    rows = load_rows()
    sets = dict(SETS)
    sets["SHORT"] = [(i, "1") for i in sorted(qs)]
    for sname in a.sets.split(","):
        for iid, rep in sets[sname]:
            out = HERE / "raw" / f"{'full' if a.full else 'replay'}_{sname}_{iid}_rep{rep}.jsonl"
            if out.exists() and any('"end": true' in l for l in open(out)):
                continue
            row = rows[(iid, rep)]
            msgs = [{"role": "user", "content": fx["prompt"].format(q=qs[iid])}]
            P = c.post(f"{U}/apply-template", json={"messages": msgs,
                                                     "chat_template_kwargs": {"reasoning_effort": "xhigh"}}).json()["prompt"]
            assert P.endswith("<think>\n"), repr(P[-40:])
            tp = c.post(f"{U}/tokenize", json={"content": P}).json()["tokens"]
            tr = c.post(f"{U}/tokenize", json={"content": P + row["reasoning"], "with_pieces": True}).json()["tokens"]
            ids = [t["id"] for t in tr]
            pieces = [t["piece"] for t in tr]
            assert ids[:len(tp)] == tp, "prompt tokenization is not a prefix of prompt+reasoning"
            bounds, last = [], -10
            for j in range(len(tp) + 1, len(ids)):
                if "\n" in pieces[j - 1] and j - last >= 2:
                    bounds.append(j); last = j
            t0 = time.time()
            with open(out, "w") as f:
                f.write(json.dumps({"meta": {"set": sname, "id": iid, "rep": rep, "status": row["status"],
                                             "finish": row.get("finish"), "n_prompt": len(tp), "n_total": len(ids),
                                             "n_bounds": len(bounds), "reasoning_chars": len(row["reasoning"])}}) + "\n")
                for k, j in enumerate(bounds + [len(ids)]):
                    end = j == len(ids)
                    forced = THINK_END if end else ids[j]
                    p = probe(c, ids[:j], forced, cache=not a.full)
                    rec = {"pos": j, "trace_pos": j - len(tp), "end": end, "next_piece": None if end else pieces[j],
                           "next_id": forced, **p}
                    if k % 25 == 0 and not a.full:   # validity gate V: the same prefix as a full prefill
                        v = probe(c, ids[:j], forced, cache=False)
                        a1 = {t[0]: t[2] for t in p["top"]}; a2 = {t[0]: t[2] for t in v["top"]}
                        shared = set(a1) & set(a2)
                        rec["V_max_abs_dlp"] = max(abs(a1[t] - a2[t]) for t in shared) if shared else None
                        rec["V_true_dlp"] = abs(p["true_lp"] - v["true_lp"])
                        rec["V_top1_same"] = p["top"][0][0] == v["top"][0][0]
                    f.write(json.dumps(rec) + "\n"); f.flush(); os.fsync(f.fileno())
            print(f"{sname:8s} {iid} rep{rep} {row['status']:16s} tokens {len(ids) - len(tp):6d} probes {len(bounds) + 1:5d} "
                  f"{time.time() - t0:6.0f}s", flush=True)


if __name__ == "__main__":
    main()
