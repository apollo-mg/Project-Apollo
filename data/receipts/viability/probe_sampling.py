#!/usr/bin/env python3
"""Does greedy decoding cause the NO-STOP failures, or does the model?

CARD_CROSSCHECK: every fixture run used temperature=0 / top_k=1 for determinism. The card
recommends temperature=1.0, top_p=0.95, top_k=20 for thinking mode, and greedy decoding on a
reasoning model is a documented cause of exactly the NO-STOP signature. This is the deciding
arm, run in the ONE cell where the failure was actually observed: .194 / Q6_K / xhigh / CAL-U5.

Recommended sampling is non-deterministic, so it gets repeats. Greedy gets one — it is
deterministic and has already been observed twice.
"""
import json, sys, time, urllib.request

HOST = sys.argv[1] if len(sys.argv) > 1 else "http://10.0.0.194:8080"
FX = json.load(open("fixture_v0_beta.json"))["tier_cal"]
ITEM = next(i for i in FX["items"] if i["id"] == "CAL-U5")
NPRED = 6144            # the budget CAL-U5 failed at, twice, on this exact box+quant

CONDS = [
    ("greedy (ours)      ", {"temperature": 0, "top_k": 1}, 1),
    ("card thinking-mode ", {"temperature": 1.0, "top_p": 0.95, "top_k": 20, "min_p": 0.0,
                             "presence_penalty": 0.0}, 3),
]

def ask(samp):
    body = {"messages": [{"role": "user", "content": FX["prompt"].format(q=ITEM["q"])}],
            "n_predict": NPRED, "chat_template_kwargs": {"reasoning_effort": "xhigh"}, **samp}
    req = urllib.request.Request(HOST.rstrip("/") + "/v1/chat/completions",
                                 data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=300 + NPRED / 2.5) as r:
        d = json.loads(r.read())
    m = d["choices"][0]["message"]
    c, rz = (m.get("content") or ""), (m.get("reasoning_content") or "")
    fin = d["choices"][0].get("finish_reason")
    line = [l for l in (c + "\n" + rz).splitlines() if "exact answer" in l.lower()]
    ans = line[-1].split(":", 1)[1].strip() if line else ""
    return ans, fin, len(c) + len(rz), time.time() - t0

print(f"CAL-U5 @ {HOST}  |  Q6_K, xhigh, n_predict={NPRED}  |  the cell where NO-STOP was observed")
print(f"item: {ITEM['q']}\n")
for label, samp, reps in CONDS:
    for i in range(reps):
        try:
            ans, fin, n, dt = ask(samp)
        except Exception as e:
            print(f"  {label} #{i+1}  ERROR {type(e).__name__}"); continue
        verdict = ("NO-STOP" if fin == "length" and not ans
                   else "ABSTAINED" if ans.strip().upper().startswith("UNKNOWN")
                   else "ANSWERED" if ans else "NO-ANSWER")
        print(f"  {label} #{i+1}  {verdict:<10} {n:>6,} chars  {dt:>5.0f}s  "
              f"fin={fin}  ans={ans[:34]!r}", flush=True)
