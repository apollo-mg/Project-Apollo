#!/usr/bin/env python3
"""Does the Hermes gateway honour a per-request seed?

Corpus v2 relies on PAIRED SEEDS: the same seed set across every arm, so comparisons
are paired rather than independent. That is worth real statistical power -- and it is
worth exactly NOTHING if the gateway drops the field on the floor.

`gateway_transport.chat_stream` posts only {"message": ...}; sampling config lives
gateway-side. llama-server itself DOES honour a per-request seed (verified 2026-09-20:
24 byte-identical generations via /v1/chat/completions with seed=12345). Whether Hermes
forwards one is untested, and a silently-ignored parameter is the textbook
readiness-probes-lie failure: everything returns 200 and the pairing is imaginary.

Three-way test, because two of the outcomes look alike:

  A1 vs A2  (same seed, twice)      identical => reproducible
  A  vs B   (different seeds)       differ    => the seed actually CONTROLS sampling

  identical/differ  -> seed is honoured.                     Paired seeds are real.
  differ/differ     -> seed is IGNORED, sampling is free.    Paired seeds impossible.
  identical/identical -> gateway pins its own fixed seed.    Reproducible, but the seed
                         is not a lever: every arm sees one draw, so pairing is trivial
                         and K>1 buys nothing. Must be known before choosing K.

Usage: probe_gateway_seed.py [base] [key]
"""
import sys, json, hashlib, re
import gateway_transport as gw

# THE GUARD THIS PROBE SHIPPED WITHOUT, and immediately needed. First run returned three
# byte-identical outputs and scored "GATEWAY PINS ITS OWN SEED". The identical string was
# "API call failed after 3 retries: Connection error." -- the gateway could not reach a
# model at all. Three identical ERRORS are not three identical generations.
# driver.py already carries exactly this pattern; the probe did not, and turned an
# infrastructure failure into a determinism verdict. Same class as the false-pass guard
# in judge(): a result that cannot distinguish success from absence is not a result.
INFRA_PAT = re.compile(
    r"API call failed|HTTP [45]\d\d|upstream command exited|connection refused|"
    r"Request timed out|no such model|failed to load", re.I)
MIN_LEN = 200   # a 120-word answer is ~600 chars; anything near an error string is suspect

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8643"
KEY  = sys.argv[2] if len(sys.argv) > 2 else "argus-local-test-key-0123456789"

# High-entropy prompt on purpose: a confident task returns the same tokens under any
# perturbation and cannot distinguish "seeded" from "ignored". See
# data/receipts/argus-v2/RESULT_TENSOR_SPLIT_DETERMINISM.md.
MSG = "Write a vivid 120-word description of an abandoned lighthouse at dawn. Be specific and original."

def run(tag, seed):
    sid = gw.new_session(BASE, KEY, f"seedprobe-{tag}-{seed}")
    text, _tools, failed = gw.chat_stream(BASE, KEY, sid, MSG, timeout=600, seed=seed)
    infra = bool(INFRA_PAT.search(text)) or (len(text) < MIN_LEN)
    return {"tag": tag, "seed": seed, "failed": failed, "len": len(text), "infra": infra,
            "sha": hashlib.sha256(text.encode()).hexdigest()[:16], "head": text[:70]}

if __name__ == "__main__":
    rs = [run("A1", 12345), run("A2", 12345), run("B", 99999)]
    for r in rs:
        print(f"  {r['tag']:3s} seed={r['seed']:<6} {r['sha']} len={r['len']:4d} failed={r['failed']}")
    if any(r["infra"] for r in rs):
        print(" VERDICT: VOID -- infrastructure failure, not a determinism result.")
        print("   The gateway is up but could not reach a model, or returned something too")
        print("   short to be an answer. Point hermes-agent at a live endpoint and re-run.")
        print("   (Only :8099, the wake proxy, served /v1/models locally at last check.)")
        print(json.dumps(rs, indent=1))
        sys.exit(2)
    same = rs[0]["sha"] == rs[1]["sha"]
    diff = rs[0]["sha"] != rs[2]["sha"]
    print()
    if same and diff:   v = "SEED HONOURED -- paired seeds are real"
    elif not same:      v = "SEED IGNORED -- sampling is free-running; paired seeds IMPOSSIBLE, raise K or pin server-side"
    else:               v = "GATEWAY PINS ITS OWN SEED -- reproducible but the seed is not a lever; K>1 buys nothing"
    print(" VERDICT:", v)
    print(json.dumps(rs, indent=1))
