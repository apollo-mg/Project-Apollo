#!/usr/bin/env python3
"""Does an anti-guessing clause in the SYSTEM block fix xhigh's instability?

Established: the tier_cal user prompt ALREADY contains an explicit hatch ("...your answer
must be the single word UNKNOWN"), and xhigh fabricates on false-premise items anyway. So a
system-injected "validate key assumptions, consider plausible alternatives" outcompetes a
user-level instruction to abstain.

Mark's hypothesis: the counterweight has to live in the same place as the instruction it is
counterweighting. The template renders reasoning_instructions FIRST, then merged_system — so
a system message lands directly after the xhigh text, in the same block.

Items are the three that flipped between seeds under xhigh, plus CAL-U3 which fails at every
effort. 3 seeds x 2 conditions.
"""
import json, sys, urllib.request, collections

HOST = sys.argv[1] if len(sys.argv) > 1 else "http://10.0.0.194:8080"
FX = json.load(open("fixture_v0_beta.json"))["tier_cal"]
IDS = ["CAL-U3", "CAL-U4", "CAL-U5", "CAL-U8"]
ITEMS = [i for i in FX["items"] if i["id"] in IDS]
SEEDS = [2001, 2002, 2003]
COUNTERWEIGHT = ("Do not guess. If the entity, event or work named in a question does not "
                 "exist, or the question rests on a false premise, say so plainly rather than "
                 "producing a plausible-sounding answer. An unsupported specific answer is "
                 "worse than admitting the thing does not exist.")

def ask(item, seed, system):
    msgs = ([{"role": "system", "content": system}] if system else []) + \
           [{"role": "user", "content": FX["prompt"].format(q=item["q"])}]
    body = {"messages": msgs, "n_predict": 6144, "temperature": 1.0, "top_p": 0.95,
            "top_k": 20, "min_p": 0.0, "seed": seed,
            "chat_template_kwargs": {"reasoning_effort": "xhigh"}}
    req = urllib.request.Request(HOST.rstrip("/") + "/v1/chat/completions",
                                 data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=2800) as r:
        d = json.loads(r.read())
    m = d["choices"][0]["message"]
    c, rz = (m.get("content") or ""), (m.get("reasoning_content") or "")
    fin = d["choices"][0].get("finish_reason")
    line = [l for l in (c or rz).splitlines() if "exact answer" in l.lower()]
    ans = line[-1].split("Answer:", 1)[-1].strip() if line else ""
    if fin == "length" and not ans: return "NO-STOP", "", len(c) + len(rz)
    if ans.upper().startswith("UNKNOWN"): return "ABSTAINED", ans, len(c) + len(rz)
    return ("ANSWERED-WRONG" if ans else "NO-ANSWER"), ans, len(c) + len(rz)

print(f"xhigh + system counterweight  |  {HOST}  |  seeds {SEEDS}\n")
tally = collections.Counter()
for label, sysmsg in (("baseline (no system msg)", None), ("+ counterweight", COUNTERWEIGHT)):
    print(f"  === {label} ===")
    for it in ITEMS:
        row = []
        for s in SEEDS:
            try:
                v, ans, n = ask(it, s, sysmsg)
            except Exception as e:
                v, ans, n = f"ERR:{type(e).__name__}", "", 0
            row.append(v)
            tally[(label, v)] += 1
        print(f"    {it['id']:<8} " + "  ".join(f"{v:<15}" for v in row), flush=True)
    ok = tally[(label, "ABSTAINED")]
    print(f"    -> ABSTAINED {ok}/{len(ITEMS)*len(SEEDS)}\n")
