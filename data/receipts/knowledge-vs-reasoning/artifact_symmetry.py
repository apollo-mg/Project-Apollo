#!/usr/bin/env python3
"""G-5-style SYMMETRY CHECK on grader artifacts -- the one we never ran.

The committed -36.8pp knowledge result assumes the deterministic grader is arm-neutral. It is
neutral by construction for *phrasing*, but not necessarily for a STYLE SHIFT. Observed in the
CORRECT->WRONG dump: the pruned arm answers "Kepler." / "Faraday." / "Pauli ..." where the base
arm answers "Johannes Kepler." / "Michael Faraday." Gold carries the forename, so substring
matching books the pruned arm WRONG for an answer a human grades CORRECT.

If that clipping is asymmetric -- and it looks asymmetric -- some of the -36.8pp is the pruned
model becoming TERSER, not less knowledgeable. Same failure class as the thinking-mode confound
and the numpy fail-green: an arm-correlated measurement artifact masquerading as signal.

Counted here, per arm, over ALL probes (not just the transition set):
  PARTIAL_HIT = verdict WRONG *and* the response contains >=1 content token of the gold.
That is an over-inclusive proxy (it catches "Hanso Bauer" for "Mossbauer" too), so it is an
UPPER BOUND on artifact rate. What matters is whether the bound is symmetric across arms.
"""
import json, re, sys
from collections import defaultdict

sys.path.insert(0, "/mnt/TG_2TB/Projects/Apollo/data/receipts/ikp")
from ikp_score import grade, norm

EXCLUDE = {"researcher"}
STOP = {"the", "a", "an", "of", "in", "is", "was", "by", "and", "de", "la", "von", "who",
        "mount", "river", "city", "island", "first", "written", "also", "known", "as", "it",
        "for", "to", "at", "on", "that", "with", "year", "name", "largest", "highest"}

ARMS = [("base", ["ikp_glm_base_rep2.jsonl"]), ("pruned", ["ikp_glm_reap_rep1.jsonl"])]


def toks(s):
    return [t for t in norm(s).split() if t not in STOP and len(t) > 2]


for label, paths in ARMS:
    n_wrong = 0
    partial = []
    for path in paths:
        for line in open(path):
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            if r.get("source_type") in EXCLUDE:
                continue
            v, _ = grade(r["gold"], r.get("response", ""), 25, r.get("finish_reason"))
            if v != "WRONG":
                continue
            n_wrong += 1
            gt = toks(r["gold"])
            rn = norm(r.get("response", ""))
            hits = [t for t in gt if re.search(rf"(?<!\w){re.escape(t)}(?!\w)", rn)]
            # short-prefix truncation too: "mek" <- "mekong", missed by a len>=4 rule
            if not hits:
                for g in gt:
                    for w in rn.split():
                        if 3 <= len(w) < len(g) and g.startswith(w):
                            hits.append(f"{g}~{w}")
                            break
                    if hits:
                        break
            if hits:
                partial.append((r["gold"][:30], (r.get("response") or "").strip()[:52], hits[0]))
    rate = len(partial) / n_wrong if n_wrong else 0
    print(f"\n=== {label:<7} WRONG={n_wrong:4d}   PARTIAL_HIT={len(partial):3d}  ({rate:.1%} of WRONG)")
    for g, resp, h in partial[:18]:
        print(f"      {g:<30} -> {resp:<52} [{h}]")
