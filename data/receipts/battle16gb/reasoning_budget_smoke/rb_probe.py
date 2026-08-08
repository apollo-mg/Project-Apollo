#!/usr/bin/env python3
"""Probe one (model, reasoning-budget) cell for PREREG_REASONING_BUDGET_SMOKE.md.

Primary discriminator is STRUCTURAL: does the server populate `reasoning_content`?
Absent reasoning at budget 0 only means "the flag worked" if budget -1 PROVED the template
emits reasoning in the first place (gate G-RB0) -- otherwise a silently-dropped thinking
path is indistinguishable from an honoured budget. The driver enforces that ordering.

Usage: rb_probe.py --endpoint URL --label L --budget N --prompts P.json --out O.jsonl
"""
import argparse, json, sys, urllib.request, urllib.error

ap = argparse.ArgumentParser()
ap.add_argument("--endpoint", required=True)
ap.add_argument("--label", required=True)
ap.add_argument("--budget", required=True)
ap.add_argument("--prompts", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--max-tokens", type=int, default=2048)
a = ap.parse_args()

prompts = json.load(open(a.prompts))
rows = []
# Append each row as it lands: a killed or timed-out cell then keeps the responses it paid
# for instead of discarding all of them. (Four background kills earlier today lost nothing
# only because those cells happened to complete.)
sink = open(a.out, "w", buffering=1)

for i, p in enumerate(prompts):
    body = json.dumps({
        "messages": [{"role": "user", "content": p["prompt"]}],
        "temperature": 0, "top_k": 1, "max_tokens": a.max_tokens, "stream": False,
    }).encode()
    req = urllib.request.Request(a.endpoint.rstrip("/") + "/v1/chat/completions",
                                 data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=900) as r:
            j = json.loads(r.read())
        ch = j["choices"][0]
        msg = ch.get("message", {})
        rc = msg.get("reasoning_content") or ""
        ct = msg.get("content") or ""
        usage = j.get("usage", {})
        row = dict(label=a.label, budget=a.budget, doc_id=p["doc_id"],
                   n_constraints=p["n_constraints"],
                   reasoning_chars=len(rc), content_chars=len(ct),
                   has_reasoning=bool(rc.strip()), has_content=bool(ct.strip()),
                   finish_reason=ch.get("finish_reason"),
                   completion_tokens=usage.get("completion_tokens"),
                   prompt_tokens=usage.get("prompt_tokens"),
                   reasoning_head=rc[:400], content_head=ct[:400])
    except Exception as e:
        row = dict(label=a.label, budget=a.budget, doc_id=p["doc_id"],
                   n_constraints=p["n_constraints"], error=f"{type(e).__name__}: {e}",
                   has_reasoning=None, has_content=None)
    rows.append(row)
    sink.write(json.dumps(row) + "\n")
    print(f"  [{i+1}/{len(prompts)}] doc {row['doc_id']:<4} "
          f"reason={row.get('reasoning_chars','ERR')} content={row.get('content_chars','ERR')} "
          f"tok={row.get('completion_tokens')} fin={row.get('finish_reason')}", flush=True)

sink.close()

ok = [r for r in rows if "error" not in r]
nr = sum(1 for r in ok if r["has_reasoning"])
nc = sum(1 for r in ok if r["has_content"])
toks = [r["completion_tokens"] for r in ok if r.get("completion_tokens") is not None]
rch = [r["reasoning_chars"] for r in ok]
print(f"=== {a.label} budget={a.budget}: {len(ok)}/{len(rows)} ok | "
      f"with_reasoning={nr}/{len(ok)} | with_content={nc}/{len(ok)} | "
      f"mean_completion_tokens={sum(toks)/len(toks):.0f}" if toks else "n/a",
      f"| mean_reasoning_chars={sum(rch)/len(rch):.0f}" if rch else "", flush=True)

# Exit non-zero only on transport failure, never on a scientific outcome.
sys.exit(0 if ok else 1)
