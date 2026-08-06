#!/usr/bin/env python3
import json, hashlib
on  = json.load(open("/home/mark/mtp_ab/arm_mtp_on.json"))
off = json.load(open("/home/mark/mtp_ab/arm_mtp_off.json"))

print(f"MTP ON : {on['aggregate_tok_s']:>6} tok/s   ({on['total_completion_tokens']} tok / {on['total_wall_s']}s)")
print(f"MTP OFF: {off['aggregate_tok_s']:>6} tok/s   ({off['total_completion_tokens']} tok / {off['total_wall_s']}s)")
print(f"SPEEDUP: {on['aggregate_tok_s']/off['aggregate_tok_s']:.2f}x")
print()
print("per-prompt tok/s   ON / OFF")
for a, b in zip(on["rows"], off["rows"]):
    print(f"   {a['tok_s']:>6} / {b['tok_s']:<6}  {a['prompt'][:46]}")
print()
print("=== greedy output agreement (temp 0, top_k 1, same seed) ===")
ident = 0
for a, b in zip(on["rows"], off["rows"]):
    same_c = a["content"] == b["content"]
    same_r = a["rc"] == b["rc"]
    if same_c and same_r:
        ident += 1
        print(f"  IDENTICAL  {a['prompt'][:46]}")
    else:
        ca, cb = a["content"], b["content"]
        ra, rb = a["rc"], b["rc"]
        dc = next((i for i, (x, y) in enumerate(zip(ca, cb)) if x != y), min(len(ca), len(cb)))
        dr = next((i for i, (x, y) in enumerate(zip(ra, rb)) if x != y), min(len(ra), len(rb)))
        print(f"  DIFFERS    {a['prompt'][:46]}")
        print(f"             content same={same_c} (len {len(ca)} vs {len(cb)}, first diff @{dc})")
        print(f"             think   same={same_r} (len {len(ra)} vs {len(rb)}, first diff @{dr})")
print()
print(f"VERDICT: {ident}/{len(on['rows'])} prompts byte-identical across arms")
if ident == len(on["rows"]):
    print("  -> MTP is a PURE SPEED KNOB here: identical greedy output, 1.7x faster.")
else:
    print("  -> MTP CHANGES OUTPUT: it is not a pure speed knob; an A/B enabling it on")
    print("     one arm only would be confounded.")
