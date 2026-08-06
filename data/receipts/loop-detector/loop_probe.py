#!/usr/bin/env python3
"""Does compression ratio separate degeneration loops from legitimately long reasoning?

Background: the temp-0 Laguna leg stratified truncations by gzip ratio — loops came out
< 0.08, coherent-but-capped > 0.12. That threshold was derived on ONE model at Q2. Before
building a streaming abort on top of it, it has to be shown to generalise.

This collects reasoning traces WITH their compression ratios and outcomes, so the question
can be answered from the distribution instead of from the prior:

  H1  cap-hitters (finish=length) have systematically lower gzip ratio than terminators
  H2  the ratio is bimodal, i.e. there is an actual threshold rather than a continuum

A detector needs BOTH. If the ratio merely correlates with length, any threshold trades
recovered wedges for aborted good reasoning at a rate we'd have to measure anyway.

Env: LP_ENDPOINT LP_MODEL LP_TAG LP_K LP_MAXTOK LP_TEMP LP_TOP_P LP_TOP_K LP_PROBLEMS
"""
import json, urllib.request, os, sys, time, gzip, io

EP      = os.environ["LP_ENDPOINT"]
MODEL   = os.environ.get("LP_MODEL", "unknown")
TAG     = os.environ.get("LP_TAG", "lp")
K       = int(os.environ.get("LP_K", "2"))
MAXTOK  = int(os.environ.get("LP_MAXTOK", "16000"))
TEMP    = float(os.environ.get("LP_TEMP", "0.7"))
TOP_P   = os.environ.get("LP_TOP_P")
TOP_K   = os.environ.get("LP_TOP_K")
HERE    = os.path.dirname(os.path.abspath(__file__))

allp = {json.loads(l)["task_id"]: json.loads(l)
        for l in open(os.path.join(HERE, "humanevalplus.jsonl"))}
want = os.environ.get("LP_PROBLEMS", "").split(",")
problems = [allp[t] for t in want if t in allp]
if not problems:
    sys.exit("no problems selected")

def gzip_ratio(s):
    """Compressed size / raw size. Repetitive text compresses hard -> low ratio."""
    b = s.encode("utf-8", "replace")
    if len(b) < 200:
        return None                      # too short to be meaningful
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb", compresslevel=6) as f:
        f.write(b)
    return len(buf.getvalue()) / len(b)

def call(prompt):
    payload = {"messages": [{"role": "user", "content": prompt}],
               "temperature": TEMP, "max_tokens": MAXTOK}
    if TOP_P: payload["top_p"] = float(TOP_P)
    if TOP_K: payload["top_k"] = int(TOP_K)
    req = urllib.request.Request(EP, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=3600) as r:
        d = json.loads(r.read())
    ch = d["choices"][0]; m = ch["message"]
    return {"finish": ch.get("finish_reason"),
            "content": m.get("content") or "", "rc": m.get("reasoning_content") or "",
            "out_tok": (d.get("usage") or {}).get("completion_tokens"),
            "wall_s": round(time.time() - t0, 1)}

rows = []
tdir = os.path.join(HERE, f"loop_traces_{TAG}")
os.makedirs(tdir, exist_ok=True)

for p in problems:
    for k in range(K):
        try:
            r = call(p["prompt"])
        except Exception as e:
            print(f"  {p['task_id']} k{k}: ERROR {e}", flush=True); continue
        gr_rc = gzip_ratio(r["rc"])
        rows.append({"task_id": p["task_id"], "k": k, "finish": r["finish"],
                     "out_tok": r["out_tok"], "wall_s": r["wall_s"],
                     "rc_chars": len(r["rc"]), "content_chars": len(r["content"]),
                     "gzip_ratio_rc": None if gr_rc is None else round(gr_rc, 4)})
        # every trace is kept, not just failures — the whole point is the distribution
        fn = f"{p['task_id'].replace('/', '_')}.k{k}.{r['finish']}.txt"
        with open(os.path.join(tdir, fn), "w") as f:
            f.write(f"### {p['task_id']} k={k} finish={r['finish']} out_tok={r['out_tok']} "
                    f"gzip_ratio={gr_rc}\n### REASONING:\n{r['rc']}\n### CONTENT:\n{r['content']}\n")
        print(f"  {p['task_id']:16s} k{k} finish={r['finish']:<7s} tok={r['out_tok']:<6} "
              f"rc={len(r['rc']):<7} gzip={gr_rc}", flush=True)

out = {"model": MODEL, "tag": TAG, "endpoint": EP, "K": K, "max_tokens": MAXTOK,
       "temp": TEMP, "top_p": TOP_P, "top_k": TOP_K, "n_rows": len(rows), "rows": rows}
json.dump(out, open(os.path.join(HERE, f"loop_probe_{TAG}.json"), "w"), indent=2)

caps = [r for r in rows if r["finish"] == "length" and r["gzip_ratio_rc"]]
term = [r for r in rows if r["finish"] != "length" and r["gzip_ratio_rc"]]
def med(v):
    s = sorted(v); return s[len(s)//2] if s else None
print(f"\n=== {MODEL} tag={TAG} ===")
print(f"cap-hitters (finish=length): n={len(caps)} median gzip={med([r['gzip_ratio_rc'] for r in caps])}")
print(f"terminators                : n={len(term)} median gzip={med([r['gzip_ratio_rc'] for r in term])}")
print(f"all gzip ratios sorted: {sorted(r['gzip_ratio_rc'] for r in rows if r['gzip_ratio_rc'])}")
print(f"-> loop_probe_{TAG}.json  +  loop_traces_{TAG}/")
