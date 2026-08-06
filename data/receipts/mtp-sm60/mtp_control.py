#!/usr/bin/env python3
"""Determinism control for the MTP A/B.

ON-vs-OFF output divergence only means something if the backend is reproducible
run-to-run with an IDENTICAL config. llama.cpp/CUDA results depend on batch shape,
and speculative decoding changes batch shape by construction — so a same-config
repeat is the only way to tell 'MTP changed the output' from 'this stack isn't
bit-reproducible anyway'.
"""
import json

def load(p):
    return json.load(open("/home/mark/mtp_ab/" + p))

off1 = load("arm_mtp_off.json")
off2 = load("arm_mtp_off_rep2.json")
on   = load("arm_mtp_on.json")
N    = len(off1["rows"])

def agree(x, y, label):
    ident = 0
    for r1, r2 in zip(x["rows"], y["rows"]):
        if r1["content"] == r2["content"] and r1["rc"] == r2["rc"]:
            ident += 1
    print("  %-24s %d/%d byte-identical" % (label, ident, N))
    return ident

print("=== DETERMINISM CONTROL (identical config, two runs) ===")
n_ctl = agree(off1, off2, "MTP-OFF run1 vs run2")
print("=== TREATMENT ===")
n_trt = agree(on, off1, "MTP-ON vs MTP-OFF")
print()
print("throughput:  ON %s | OFF %s | OFF-repeat %s  tok/s"
      % (on["aggregate_tok_s"], off1["aggregate_tok_s"], off2["aggregate_tok_s"]))
print()
if n_ctl == N:
    print("CONTROL PASSES: backend is deterministic run-to-run at temp 0.")
    print("  -> the %d/%d ON-vs-OFF divergences ARE attributable to MTP." % (N - n_trt, N))
else:
    print("CONTROL FAILS: backend is NOT reproducible run-to-run at temp 0")
    print("  (%d/%d differ with an IDENTICAL config)." % (N - n_ctl, N))
    print("  -> ON-vs-OFF divergence CANNOT be attributed to MTP. This harness cannot")
    print("     answer the exactness question. The throughput result is unaffected.")
