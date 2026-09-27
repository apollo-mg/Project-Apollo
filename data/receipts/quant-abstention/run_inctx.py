#!/usr/bin/env python3
"""In-context slot readout (PREREG_INCTX.md). One reader = one llama-server already up at --url.

For each writer arm and each M1 item whose stored main-campaign generation contains "Exact Answer:" (every graded
item; TRUNCATED and NO-ANSWER have none), the prompt is:
    the reader's own render of the CAL prompt (thinking off) + the writer's stored content up to and including the
    colon of its LAST "Exact Answer:"
/completion n_predict 1, n_probs 50, temperature 0, cache_prompt false, post_sampling_probs false (raw logits, as in
main). P_abs = P(" UNKNOWN") + P(" Unknown") + P(" unknown") from the top 50.

Probe (reader == writer only): the greedy token must be the start of what the stored generation wrote after the cut.
It cannot pass unless the render, the cut and the tokenisation reproduce the generation's own decision point.

Writes raw/inctx_<reader>__<writer>.jsonl (header + one row per usable item; flush + fsync; resumable).
"""
import argparse, json, math, os, re, sys, time
from pathlib import Path
import httpx

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "viability"))
from run_main import PROMPT, VARIANTS  # noqa: E402  (the same CAL prompt and variants as main)

CUT = re.compile(r"Exact Answer\s*:", re.I)


def writer_rows(w):
    src = HERE / "raw" / ("main_C.A.jsonl" if w == "C" else f"main_{w}.jsonl")
    return {r["id"]: r for r in map(json.loads, list(open(src))[1:])}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--reader", required=True)
    ap.add_argument("--writers", required=True, help="comma list; C = the ceiling's stored prose")
    ap.add_argument("--meta", default="{}")
    ap.add_argument("--item-arms", default="EHU", help="which item arms to read (swap passes: U)")
    ap.add_argument("--limit", type=int, default=None, help="smoke test: first N items only, output suffixed .SMOKE")
    a = ap.parse_args()
    ref = json.loads(open(HERE / "raw" / "main_C.A.jsonl").readline())      # every reader must match the ceiling's
    items = [json.loads(l) for l in open(HERE / "corpus" / "M1.jsonl")][: a.limit]
    c = httpx.Client(timeout=600)

    vt = {v: c.post(f"{a.url}/tokenize", json={"content": "Exact Answer:" + v}).json()["tokens"] for v in VARIANTS}
    base = c.post(f"{a.url}/tokenize", json={"content": "Exact Answer:"}).json()["tokens"]
    var_ids = {v: (t[len(base):][0] if len(t) == len(base) + 1 else None) for v, t in vt.items()}
    if var_ids != ref["variant_ids"]:
        sys.exit(f"UNKNOWN variant ids differ from the ceiling's: {var_ids} != {ref['variant_ids']}")

    def render(q):
        return c.post(f"{a.url}/apply-template", json={"messages": [{"role": "user", "content": PROMPT.format(q=q)}],
                      "chat_template_kwargs": {"enable_thinking": False}}).json()["prompt"]

    tail0 = render("Q")[-60:]
    if tail0 != ref["render_tail"]:
        sys.exit(f"render tail differs from the ceiling's: {tail0!r} != {ref['render_tail']!r}")
    c.post(f"{a.url}/completion", json={"prompt": render("What is the capital of France?"), "n_predict": 8,
                                         "temperature": 0, "cache_prompt": False})    # discarded warm-up

    for w in a.writers.split(","):
        W = writer_rows(w)
        out = HERE / "raw" / (f"inctx_{a.reader}__{w}.jsonl" + (".SMOKE" if a.limit else ""))
        done = {json.loads(l).get("id") for l in open(out)} if out.exists() else set()
        with open(out, "a") as f:
            if not done:
                hdr = {"header": True, "reader": a.reader, "writer": w, "meta": json.loads(a.meta),
                       "variant_ids": var_ids, "render_tail": tail0, "started": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
                f.write(json.dumps(hdr, ensure_ascii=False) + "\n"); f.flush(); os.fsync(f.fileno())
            n_probe = n_ok = 0
            for it in items:
                i = it["id"]
                if i in done or i not in W or it["arm"] not in a.item_arms:
                    continue
                ms = list(CUT.finditer(W[i]["content"]))
                if not ms:
                    continue
                cut = ms[-1].end()
                s = c.post(f"{a.url}/completion", json={"prompt": render(it["question"]) + W[i]["content"][:cut],
                           "n_predict": 1, "n_probs": 50, "temperature": 0, "cache_prompt": False,
                           "post_sampling_probs": False}).json()
                top = s["completion_probabilities"][0]["top_logprobs"]
                pv = {v: next((math.exp(t["logprob"]) for t in top if t["id"] == var_ids[v]), 0.0) for v in VARIANTS}
                tok = s.get("content", "")
                probe = None
                if a.reader == w:
                    probe = bool(tok) and W[i]["content"][cut:].startswith(tok)
                    n_probe += 1; n_ok += probe
                row = {"id": i, "arm": it["arm"], "template": it["template"], "reader": a.reader, "writer": w,
                       "P_abs": sum(pv.values()), "p_variants": pv, "slot_top": [(t["id"], t["token"], t["logprob"]) for t in top],
                       "tok": tok, "probe": probe, "writer_grade": W[i]["grade"], "writer_got": W[i]["got"],
                       "prompt_n": s.get("timings", {}).get("prompt_n")}
                f.write(json.dumps(row, ensure_ascii=False) + "\n"); f.flush(); os.fsync(f.fileno())
                print(f"{a.reader}<-{w} {i} P_abs={row['P_abs']:.3f} tok={tok!r} probe={probe}", flush=True)
            if a.reader == w:
                print(f"PROBE {a.reader}: {n_ok}/{n_probe}", flush=True)


if __name__ == "__main__":
    main()
