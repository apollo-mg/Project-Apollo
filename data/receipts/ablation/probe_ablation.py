#!/usr/bin/env python3
"""How much of xhigh's effect is SEMANTICS, and how much is just having a system message?

Qwen3.8's xhigh setting injects 207 characters. Measured effect vs medium (which injects
NOTHING — it is the unmodified model, not a midpoint): 5.85x token cost, abstention 7/8 -> 3/8,
and seed-stable results becoming unstable.

Everything here runs at effort=medium so the template injects nothing, and the string under
test is supplied as a system message — which the template renders in exactly the position
reasoning_instructions would occupy (verified 2026-08-21).

  none     baseline: the unmodified model
  full     the real xhigh string, 207 chars
  neutral  211 chars of semantically empty text  <-- THE CONTROL. If this reproduces the
           effect, it is not the meaning, it is the presence of a system message at all.
  C1/C2/C3 single clauses, to find which one carries the effect
"""
import json, os, sys, urllib.request
from concurrent.futures import ThreadPoolExecutor

HOST = sys.argv[1] if len(sys.argv) > 1 else "http://10.0.0.194:8080"
FX = None if False else \
     json.load(open("../viability/fixture_v0_beta.json"))["tier_cal"]
IDS = ["CAL-U1","CAL-U2","CAL-U3","CAL-U4","CAL-U5","CAL-U8"]
ITEMS = [i for i in FX["items"] if i["id"] in IDS]
SEEDS = [6001, 6002]

FULL = ("Reasoning effort is set to xhigh. Please think carefully through the task, validate key "
        "assumptions, consider plausible alternatives, and prioritize correctness, consistency, "
        "and clarity in the final answer.")
NEUTRAL = ("Reasoning effort is set to xhigh. The current session identifier is 7413-QX. This "
           "request originated from a standard client and no special handling applies to it "
           "beyond the ordinary defaults for this deployment.")
CONDS = [("none", None), ("full", FULL), ("neutral", NEUTRAL),
         ("C1_think_carefully", "Please think carefully through the task."),
         ("C2_validate_assumptions", "Validate key assumptions."),
         ("C3_consider_alternatives", "Consider plausible alternatives.")]

SINK = open("ablation_results.jsonl", "a", encoding="utf-8")
import threading
LOCK = threading.Lock()

def run(args):
    cond, sysmsg, it, seed = args
    msgs = ([{"role":"system","content":sysmsg}] if sysmsg else []) + \
           [{"role":"user","content":FX["prompt"].format(q=it["q"])}]
    body = {"messages":msgs,"n_predict":6144,"temperature":1.0,"top_p":0.95,"top_k":20,
            "seed":seed,"chat_template_kwargs":{"reasoning_effort":"medium"}}
    r = urllib.request.Request(HOST.rstrip("/")+"/v1/chat/completions",
        data=json.dumps(body).encode(), headers={"Content-Type":"application/json"})
    try:
        with urllib.request.urlopen(r, timeout=2800) as f: d=json.loads(f.read())
    except Exception as e:
        return dict(cond=cond,id=it["id"],seed=seed,verdict=f"ERR:{type(e).__name__}",chars=0)
    m=d["choices"][0]["message"]; c=m.get("content") or ""; rz=m.get("reasoning_content") or ""
    fin=d["choices"][0].get("finish_reason")
    lines=[l for l in (c or rz).splitlines() if "exact answer" in l.lower()]
    ans=lines[-1].split("Answer:",1)[-1].strip() if lines else ""
    v = ("NO-STOP" if fin=="length" and not ans else
         "ABSTAINED" if ans.upper().startswith("UNKNOWN") else
         "ANSWERED-WRONG" if ans else "NO-ANSWER")
    rec=dict(cond=cond,id=it["id"],seed=seed,verdict=v,chars=len(c)+len(rz),ans=ans[:80],sys_len=len(sysmsg or ""))
    with LOCK:
        SINK.write(json.dumps(rec)+"\n"); SINK.flush(); os.fsync(SINK.fileno())
    return rec

jobs=[(cn,cs,it,s) for cn,cs in CONDS for it in ITEMS for s in SEEDS]
print(f"{len(jobs)} cells: {len(CONDS)} conditions x {len(ITEMS)} items x {len(SEEDS)} seeds")
with ThreadPoolExecutor(max_workers=4) as ex:      # server has 4 slots
    for n,rec in enumerate(ex.map(run,jobs),1):
        if n%12==0: print(f"  {n}/{len(jobs)} done",flush=True)
print("complete")
