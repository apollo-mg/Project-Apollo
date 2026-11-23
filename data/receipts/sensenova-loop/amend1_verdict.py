#!/usr/bin/env python3
"""PREREG_SENSENOVA_LOOP Amendment 1 verdict: the reference's 20-chunk wikitext perplexity against llama.cpp's
(Q8_0, GPU, the same chunks: 17.5441 at chunk 20 of raw/ppl_SNL.log). Accept within 5 %. Refuses to decide unless the
reference JSON holds exactly 20 chunks. Writes raw/amend1_verdict.txt (first word ACCEPT or REJECT).
Usage: amend1_verdict.py"""
import json, re, sys
from pathlib import Path

H = Path(__file__).resolve().parent
r = json.load(open(H / "raw" / "reference" / "ref_ppl_20.json"))
if len(r["chunks"]) != 20:
    sys.exit(f"NOT DECIDED: the reference holds {len(r['chunks'])} chunks, not 20")
ll = {int(a): float(b) for a, b in re.findall(r"\[(\d+)\]([0-9.]+)", open(H / "raw" / "ppl_SNL.log").read())}
print("chunk  reference  llama.cpp  ratio")
for c in r["chunks"]:
    print(f"{c['chunk']:5d}  {c['running_ppl']:9.4f}  {ll[c['chunk']]:9.4f}  {ll[c['chunk']] / c['running_ppl']:.4f}")
ref, lc = r["final_ppl"], ll[20]
lo, hi = lc / 1.05, lc * 1.05
verdict = "ACCEPT" if lo <= ref <= hi else "REJECT"
line = (f"{verdict} reference {ref:.4f} vs llama.cpp {lc:.4f} (ratio {lc / ref:.4f}; band {lo:.2f}-{hi:.2f}), 20 chunks, "
        f"torch {r['torch']}, transformers {r['transformers']}")
print("\n" + line)
open(H / "raw" / "amend1_verdict.txt", "w").write(line + "\n")
