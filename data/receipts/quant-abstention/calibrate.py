#!/usr/bin/env python3
"""Calibrate YOUR Qwen3.8-27B quant's abstention offset against this campaign's Q8_0 reference (CALIB method).

Everything this needs already ships in this directory: the 240-item corpus (`corpus/M1.jsonl`), the runner
(`run_main.py`) and the Q8_0 reference rows (`raw/main_C.A.jsonl`, `raw/main_C.B.jsonl`, one per .194 lane; they fit
b = 0 against each other, the identity control in RESULT_CALIB.md).

1. Serve your file with llama-server, thinking off, one slot, f16 KV (the flags in `serve_main.sh`), and collect the
   slot readout with this campaign's own runner. It writes `raw/main_MINE.jsonl`:

       ./run_main.py --url http://HOST:PORT --arm MINE --meta '{"model": "your-file.gguf"}'

2. Fit your offset:

       ./calibrate.py raw/main_MINE.jsonl

   It prints b, the logit bias to add to the three UNKNOWN token ids, and your file's timidity (refusing answerable
   hard questions) and confabulation (answering invented ones) against Q8_0, before and after.

   To apply it in llama-server, send "logit_bias": [[59322, b], [21024, b], [9496, b]].

SCOPE -- read before using b (RESULT_CALIB.md, RESULT_INCTX.md):
  * b corrects the FORCED answer slot: P(UNKNOWN) when the prompt is followed straight by "Exact Answer:". Use it
    when you read that probability directly (a classifier, a gate, a logprob threshold).
  * It is not a fix for generated answers. In generation the decision is made in the sentence the model writes
    first, and most files that look "confident" in the slot refuse at Q8_0's rate when they generate.
  * One model family (Qwen3.8-27B: the token ids and the reference are its own), thinking off, this prompt. A
    different model needs its own reference run.
"""
import argparse, json, sys
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from analyze_calib import Data, T, VAR_IDS, GRID, bounds, shift, fit_b  # noqa: E402  (the registered code)


def load(path):
    rows = [json.loads(l) for l in open(path)]
    return rows[0], {r["id"]: r for r in rows[1:] if "id" in r}


def rates(D, p, pc):
    H, U, E = D.arm == "H", D.arm == "U", D.arm == "E"
    return {"timid_H": float((p[H] - pc[H]).mean()), "confab_U": float((pc[U] - p[U]).mean()),
            "easy_E": float((p[E] - pc[E]).mean())}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mine", help="your run_main.py output (raw/main_<ARM>.jsonl)")
    ap.add_argument("--ref", default="A", choices="AB", help="which Q8_0 reference lane (default A; they agree)")
    a = ap.parse_args()
    items = {x["id"]: x for x in map(json.loads, open(HERE / "corpus" / "M1.jsonl"))}
    rh, ref = load(HERE / "raw" / f"main_C.{a.ref}.jsonl")
    mh, mine = load(a.mine)

    ids = sorted(set(items) & set(ref) & set(mine))
    if len(ids) < len(items):
        sys.exit(f"your run has {len(set(items) & set(mine))} of the {len(items)} corpus items; finish the run first")
    if sorted(mh.get("variant_ids", {}).values()) != sorted(VAR_IDS):
        sys.exit(f"your server's UNKNOWN token ids {mh.get('variant_ids')} are not {VAR_IDS}: not the same tokenizer, "
                 "so this reference does not apply")
    if mh.get("render_tail") != rh.get("render_tail"):
        print("WARNING: your prompt render differs from the reference's (chat template or thinking setting). The fit "
              "runs, but it compares two different prompts.\n")

    D = Data({i: items[i] for i in ids})
    out = {}
    for which, name in ((0, "lower"), (1, "upper")):     # a variant outside the stored top 50: both bounds, as CALIB
        pa, pc = D.vec(mine, which), D.vec(ref, which)
        b = fit_b(shift(pa[None, :], GRID[:, None]), pc, D.arm == "H", D.arm == "U")
        out[name] = {"b": b, "before": rates(D, pa, pc), "after": rates(D, shift(pa, b), pc),
                     "cells": {t: {"before": rates(Data({i: items[i] for i in ids if items[i]["template"] == t}),
                                                   pa[D.tmpl == t], pc[D.tmpl == t])} for t in T}}
    lo, hi = out["lower"], out["upper"]
    print(f"{mh.get('arm', a.mine)} vs Q8_0 (lane {a.ref}), {len(ids)} items\n")
    print(f"  b = {lo['b']:+.2f}   (upper-bound fit: {hi['b']:+.2f}; if they differ much, your file ranks UNKNOWN "
          "outside its top 50 often and b is uncertain)\n")
    print("                     before     after    (0 = Q8_0's operating point)")
    for k, label in (("timid_H", "timidity   (H)"), ("confab_U", "confabul.  (U)"), ("easy_E", "easy items (E)")):
        print(f"  {label}   {lo['before'][k]:+.3f}   {lo['after'][k]:+.3f}")
    print("\n  per template, before:  " + "  ".join(f"{t} H{c['before']['timid_H']:+.2f}/U{c['before']['confab_U']:+.2f}"
                                               for t, c in lo["cells"].items()))
    print(f"\n  llama-server: \"logit_bias\": [[59322, {lo['b']:.2f}], [21024, {lo['b']:.2f}], [9496, {lo['b']:.2f}]]")
    print("  Forced-slot readout only; see the SCOPE note at the top of this file before using b on generations.")


if __name__ == "__main__":
    main()
