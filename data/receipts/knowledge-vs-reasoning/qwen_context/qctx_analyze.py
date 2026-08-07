#!/usr/bin/env python3
"""Score the Qwen context arms against PREREG_QWEN_CONTEXT.md.

Instrument parity with the GLM legs is the whole point of this leg, so:
  * C1  -> RAW accuracy c/n, exactly as P-RAG1 was scored in rag_analyze.py
  * C3  -> COMMITTED gold/(gold+wrong), which is what RESULT_C3_CONTRADICTION.md published
           (verified: c3_analyze.py's own counts reproduce 100.0/93.4 and 93.0/33.9 this way)

Qwen3.6 is verbose and grade() books a >25-word response AMBIGUOUS *even when gold is present*
(ikp_score.py:82). On the calibration leg that moved 2.0%/3.4% of answers. So every cell also
reports a LENIENT tally (CORRECT + gold-present-but-wordy) as a DIAGNOSTIC. Predictions are
scored on the strict metric as pre-registered; the lenient column exists only to attribute a
gate failure to grounding vs verbosity, and is labelled post-hoc wherever it is quoted.
"""
import json, sys, re
from collections import defaultdict
sys.path.insert(0, "/mnt/TG_2TB/Projects/Apollo/data/receipts/ikp")
from ikp_score import grade, norm

CONDS = ("C1", "C3a", "C3b")


def load(p):
    out = defaultdict(list)
    for l in open(p):
        l = l.strip()
        if not l:
            continue
        r = json.loads(l)
        cond = r["id"].rsplit("__", 1)[1]
        resp = r.get("response") or ""
        v, why = grade(r["gold"], resp, 25, r.get("finish_reason"))
        # lenient: gold text is present, grader only demoted it for length
        lenient = v == "CORRECT" or (v == "AMBIGUOUS" and why.startswith("gold present"))
        out[cond].append({"id": r["id"], "v": v, "why": why, "lenient": lenient,
                          "resp": resp.strip(), "gold": r["gold"]})
    return out


arms = {}
for path, lab in ((sys.argv[1], "base"), (sys.argv[2], "pruned")):
    try:
        arms[lab] = load(path)
    except FileNotFoundError:
        print(f"[qctx] {lab}: {path} not present yet")
        sys.exit(1)

hdr = (f"{'arm':<8}{'cond':<6}{'n':>5}{'corr':>6}{'wrong':>6}{'refus':>7}{'ambig':>7}"
       f"{'noans':>7}{'raw':>8}{'cmtd':>8}{'lenient':>9}")
print(hdr); print("-" * len(hdr))
raw, cmtd, leni, cells = {}, {}, {}, {}
for lab in ("base", "pruned"):
    for cond in CONDS:
        vs = arms[lab].get(cond, [])
        if not vs:
            continue
        n = len(vs)
        c = sum(1 for x in vs if x["v"] == "CORRECT")
        w = sum(1 for x in vs if x["v"] == "WRONG")
        rf = sum(1 for x in vs if x["v"] == "REFUSAL")
        am = sum(1 for x in vs if x["v"] == "AMBIGUOUS")
        na = sum(1 for x in vs if x["v"] == "NO_ANSWER")
        ln = sum(1 for x in vs if x["lenient"])
        raw[(lab, cond)] = c / n
        cmtd[(lab, cond)] = c / (c + w) if (c + w) else float("nan")
        leni[(lab, cond)] = ln / n
        cells[(lab, cond)] = dict(n=n, c=c, w=w, rf=rf, am=am, na=na, ln=ln)
        print(f"{lab:<8}{cond:<6}{n:>5}{c:>6}{w:>6}{rf:>7}{am:>7}{na:>7}"
              f"{c/n:>7.1%}{cmtd[(lab,cond)]:>8.1%}{ln/n:>9.1%}")
    print("-" * len(hdr))

# ---- G-5 style termination/refusal symmetry across arms (per condition) ----
print("\n=== SPREAD CHECKS (a >2pp arm spread in noans voids an accuracy delta; G-5) ===")
for cond in CONDS:
    b, p = cells[("base", cond)], cells[("pruned", cond)]
    print(f"  {cond:<4} noans base {b['na']/b['n']:>6.1%} vs pruned {p['na']/p['n']:>6.1%}"
          f"   | refusal {b['rf']/b['n']:>6.1%} vs {p['rf']/p['n']:>6.1%}"
          f"   | ambig {b['am']/b['n']:>6.1%} vs {p['am']/p['n']:>6.1%}")

print("\n=== PREDICTION SCORING (PREREG_QWEN_CONTEXT.md §8) ===")
p_c1 = raw[("pruned", "C1")]
qx0 = p_c1 >= 0.90
print(f"  P-QX0  GATE pruned C1 >= 90%          : {p_c1:.1%} -> {'HELD' if qx0 else 'FAILED'}")
print(f"         (diagnostic, post-hoc: lenient C1 = {leni[('pruned','C1')]:.1%}; "
      f"base raw {raw[('base','C1')]:.1%}, base lenient {leni[('base','C1')]:.1%})")

os_b = abs(cmtd[("base", "C3a")] - cmtd[("base", "C3b")])
qx1 = os_b <= 0.20
print(f"  P-QX1  GATE base C3 order sens <=20pp : {os_b*100:.1f}pp -> "
      f"{'HELD' if qx1 else 'FALSIFIED'}")
print(f"         base committed: gold-1st {cmtd[('base','C3a')]:.1%}, "
      f"gold-2nd {cmtd[('base','C3b')]:.1%}")

os_p = abs(cmtd[("pruned", "C3a")] - cmtd[("pruned", "C3b")])
print(f"  P-QX2  HINGE pruned C3 order sens >=30pp: {os_p*100:.1f}pp -> ", end="")
if not (qx0 and qx1):
    print("NOT SCORED — a gate failed; C3 is not interpretable")
else:
    print(f"{'HELD' if os_p >= 0.30 else 'FALSIFIED'}")
print(f"         pruned committed: gold-1st {cmtd[('pruned','C3a')]:.1%}, "
      f"gold-2nd {cmtd[('pruned','C3b')]:.1%}")

print(f"\n  ORDER SENSITIVITY   base {os_b*100:.1f}pp   pruned {os_p*100:.1f}pp"
      f"      [GLM was: base 6.6pp, pruned 59.1pp]")

# ---- validity check: is a committed-WRONG actually the planted confabulation? ----
# If C3 WRONGs are NOT the second entry, the design isn't measuring what it claims.
try:
    probes = {r["id"]: r for r in json.load(open("qwen_ctx_probes.json"))}
    print("\n=== C3 VALIDITY: do committed-WRONG answers match the planted confabulation? ===")
    for lab in ("base", "pruned"):
        hit = miss = 0
        for cond in ("C3a", "C3b"):
            for x in arms[lab][cond]:
                if x["v"] != "WRONG":
                    continue
                q = probes.get(x["id"], {}).get("question", "")
                ents = re.findall(r"^\s*[-*\d.)\s]*(.+?)\s*$", q, re.M)
                rn = norm(x["resp"])
                if rn and any(rn in norm(e) for e in ents if e.strip()):
                    hit += 1
                else:
                    miss += 1
        tot = hit + miss
        print(f"  {lab:<7} {hit}/{tot} committed-WRONG responses appear in the supplied context"
              + ("" if not tot else f"  ({hit/tot:.0%})"))
except FileNotFoundError:
    print("\n[validity check skipped — qwen_ctx_probes.json not in cwd]")
