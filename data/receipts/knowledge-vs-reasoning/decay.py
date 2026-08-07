#!/usr/bin/env python3
"""Does the pruned model's wrong answer SHARE ITS OPENING with the right answer?

Eyeballing the 98 CORRECT->WRONG cases turned up a repeated shape:
    Tim Berners-Lee      -> "Tim Berners."
    Gabriel Garcia Marquez -> "Gabriel Garci."
    Antoine Lavoisier    -> "Antoine-Lavois"
    Igor Stravinsky      -> "Igor and Jean-Poltzer"
    William Harvey       -> "William Edward A. H. (William Edward A. H.)"
    Michael Faraday      -> "Faraday."        <- scores WRONG only because gold carries a forename
    Johannes Kepler      -> "Kepler."         <- same

i.e. the generation STARTS on the correct token sequence and decays. That is a different failure
from sampling a plausible name out of the prior ("Joseph Almasay" for Emily Bronte), and the
distinction is exactly what decides whether a healing pass is denoising or re-learning.

Measured here: token-level overlap between gold and the pruned response, restricted to the
CORRECT->WRONG set, plus a character-prefix test that catches mid-word truncation.
"""
import json, re, sys, unicodedata
from collections import Counter

sys.path.insert(0, "/mnt/TG_2TB/Projects/Apollo/data/receipts/ikp")
from ikp_score import grade, norm

EXCLUDE = {"researcher"}
STOP = {"the", "a", "an", "of", "in", "is", "was", "by", "and", "de", "la", "von", "who",
        "mount", "river", "city", "island", "first", "written", "also", "known", "as", "it",
        "for", "to", "at", "on", "that", "with", "french", "german", "italian", "british",
        "english", "american", "physicist", "painter", "composer", "artist", "novel", "year"}


def toks(s):
    return [t for t in norm(s).split() if t not in STOP and len(t) > 2]


def load(path):
    out = {}
    for line in open(path):
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        if r.get("source_type") in EXCLUDE:
            continue
        out[r["id"]] = r
    return out


base, reap = load("ikp_glm_base_rep2.jsonl"), load("ikp_glm_reap_rep1.jsonl")

cls = Counter()
examples = {k: [] for k in ("EXACT_TOKEN", "PREFIX", "NONE")}

for i in sorted(set(base) & set(reap)):
    b, p = base[i], reap[i]
    vb, _ = grade(b["gold"], b.get("response", ""), 25, b.get("finish_reason"))
    vp, _ = grade(p["gold"], p.get("response", ""), 25, p.get("finish_reason"))
    if not (vb == "CORRECT" and vp == "WRONG"):
        continue

    gt, rt = toks(b["gold"]), toks(p.get("response", ""))
    resp = (p.get("response") or "").strip()

    shared = [t for t in gt if t in rt]
    # mid-word truncation: some gold token has a >=4-char prefix that is a response token
    prefix = []
    for g in gt:
        for r in rt:
            if r != g and len(r) >= 4 and (g.startswith(r) or r.startswith(g[:max(4, len(g) - 3)])):
                prefix.append((g, r))

    if shared:
        k = "EXACT_TOKEN"
    elif prefix:
        k = "PREFIX"
    else:
        k = "NONE"
    cls[k] += 1
    if len(examples[k]) < 14:
        det = f"[{'+'.join(shared)}]" if shared else (f"[{prefix[0][0]}~{prefix[0][1]}]" if prefix else "")
        examples[k].append(f"    {b['gold'][:34]:<34} -> {resp[:58]:<58} {det}")

n = sum(cls.values())
print(f"CORRECT -> WRONG, n={n}\n")
print("=== does the wrong answer retain part of the RIGHT answer? ===============")
for k, lab in (("EXACT_TOKEN", "shares a whole content word with gold"),
               ("PREFIX", "shares a word-PREFIX (mid-word truncation)"),
               ("NONE", "shares nothing -- generated from prior")):
    print(f"  {k:<12} {cls[k]:3d} / {n}  ({cls[k]/n:4.0%})  {lab}")
print(f"\n  RESIDUAL SIGNAL (token or prefix) : {cls['EXACT_TOKEN']+cls['PREFIX']:3d} / {n} "
      f"({(cls['EXACT_TOKEN']+cls['PREFIX'])/n:.0%})")

for k in ("EXACT_TOKEN", "PREFIX", "NONE"):
    print(f"\n--- {k} " + "-" * 62)
    print("\n".join(examples[k]))
