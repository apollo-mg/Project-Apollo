#!/usr/bin/env python3
"""Informal pelican reps against a local endpoint. NOT a blind-panel arm.

Follows the precedent in `qwen4exp/pelican_informal/README.md`: same prompt and
temperature as the panel, but 3 reps with thinking off, where the panel runs 5
reps per arm with each arm's shipped template. Folding a model into the panel
needs a dated amendment and a fresh blind round with the outside raters.

Thinking-off is REQUESTED and then VERIFIED from reasoning_content, because
`enable_thinking` via chat_template_kwargs is deprecated on current buun and was
measured inert for at least one model today (RESULT_AGENTWORLD_AS_GENERATOR).
"""
import argparse, json, os, re, time, urllib.request

PROMPT = "Generate an SVG of a pelican riding a bicycle."

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8090/v1/chat/completions")
    ap.add_argument("--out", required=True)
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--max-tokens", type=int, default=8000)
    ap.add_argument("--label", required=True)
    a = ap.parse_args()

    with open(a.out, "w") as fh:
        for rep in range(1, a.reps + 1):
            payload = {"messages": [{"role": "user", "content": PROMPT}],
                       "temperature": 1.0, "max_tokens": a.max_tokens,
                       "seed": 1000 + rep,
                       "chat_template_kwargs": {"enable_thinking": False}}
            req = urllib.request.Request(a.url, data=json.dumps(payload).encode(),
                                         headers={"Content-Type": "application/json"})
            t0 = time.time()
            with urllib.request.urlopen(req, timeout=1800) as r:
                d = json.loads(r.read().decode())
            secs = time.time() - t0
            m = d["choices"][0]["message"]
            content = m.get("content") or ""
            reasoning = m.get("reasoning_content") or ""
            u = d.get("usage", {})
            tok = u.get("completion_tokens") or 0
            svgs = re.findall(r"<svg\b.*?</svg>", content, re.S | re.I)
            row = {"label": a.label, "rep": rep, "seed": 1000 + rep,
                   "secs": round(secs, 1), "completion_tokens": tok,
                   "tok_s": round(tok / secs, 2) if secs else 0,
                   "finish": d["choices"][0].get("finish_reason"),
                   "reasoning_chars": len(reasoning),   # verify, never assume
                   "content_chars": len(content),
                   "svg_count": len(svgs),
                   "svg_chars": len(svgs[0]) if svgs else 0,
                   "svg": svgs[0] if svgs else None,
                   "content": content}
            fh.write(json.dumps(row) + "\n"); fh.flush(); os.fsync(fh.fileno())
            print(f"  rep {rep}: {tok:>5} tok  {row['tok_s']:>6.2f} tok/s  {secs:>6.1f}s  "
                  f"svg={row['svg_chars']:>6} chars  reasoning={row['reasoning_chars']}  "
                  f"finish={row['finish']}")
    print(f"\nwrote {a.out}")

if __name__ == "__main__":
    main()
