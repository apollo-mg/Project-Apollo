#!/usr/bin/env python3
"""EXPLORATORY (not in PREREG_OLMO3_LADDER.md; added after the registered analysis was run and committed, 5fc794c8).

1. Template gate for Deviation 1: prompt token counts per item must be equal across OL_SFT, OL_DPO, OL_RL (OL_RL was
   served with the SFT/DPO template file); any difference means the rendering differed.
2. Hedge count: a row "answers then hedges" when its last non-empty line is exactly UNKNOWN (after stripping "Exact
   Answer:", markdown and a trailing period) and an earlier line holds a non-UNKNOWN answer (an "Exact Answer:" line, or a
   first line of at most 60 characters). One rule, all arms, all item groups. Reported next to the registered grade, and a
   stricter reading (a hedged row counts as declined) is computed only to show which predictions it would flip.
Usage: hedge_counts.py [--out RESULT_hedge.json]"""
import argparse, json, re, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent; QA = HERE.parent / "quant-abstention"
sys.path.insert(0, str(HERE.parent / "idk-lora")); from bare_rule import regrade  # noqa: E402
DEFAULT_ARMS = ("OL_SFT", "OL_DPO", "OL_RL")
def norm(line):
    s = re.sub(r"[*_`#>]", "", line).strip()
    s = re.sub(r"^exact answer\s*:\s*", "", s, flags=re.I).strip()
    return s.rstrip(".").strip()
def hedged(content):
    lines = [l for l in (content or "").splitlines() if l.strip()]
    if len(lines) < 2 or norm(lines[-1]) != "UNKNOWN": return False
    earlier = lines[:-1]
    ans = [norm(l) for l in earlier if re.match(r"\s*\**\s*exact answer\s*:", l, re.I)]
    if ans: return any(a and a.upper() != "UNKNOWN" for a in ans)
    first = norm(earlier[0])
    return bool(first) and len(first) <= 60 and first.upper() not in ("UNKNOWN",)
def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--out", default=str(HERE / "RESULT_hedge.json"))
    ap.add_argument("--arms", nargs=3, default=list(DEFAULT_ARMS), help="11-25: three arms, ladder order (default the Instruct ladder, unchanged)"); a = ap.parse_args()
    ARMS = tuple(a.arms)
    items = {x["id"]: x for x in map(json.loads, open(QA / "corpus" / "M1.jsonl"))}
    R = {arm: {r["id"]: r for r in map(json.loads, open(QA / "raw" / f"main_{arm}.jsonl")) if "id" in r} for arm in ARMS}
    pt = {arm: {i: (r.get("gen_usage") or {}).get("prompt_tokens") for i, r in R[arm].items()} for arm in ARMS}
    diff = [i for i in items if len({pt[arm][i] for arm in ARMS}) != 1]
    nonnull = all(pt[arm][i] is not None for arm in ARMS for i in items)
    out = {"template_gate": {"items": len(items), "prompt_tokens_differ": diff, "all_recorded": nonnull}, "arms": {}}
    print(f"template gate: prompt tokens equal across arms on {len(items) - len(diff)}/{len(items)} items (all recorded: {nonnull})")
    for arm in ARMS:
        o = {}
        for k in "EHU":
            ids = [i for i in items if items[i]["arm"] == k]
            g = {i: regrade(items[i], R[arm][i]) for i in ids}; h = [i for i in ids if hedged(R[arm][i].get("content"))]
            o[k] = {"hedged": len(h), "hedged_by_grade": {gr: sum(g[i] == gr for i in h) for gr in sorted({g[i] for i in h})},
                    "declined_registered": sum(g[i] == "ABSTAINED" for i in ids),
                    "declined_strict": sum(g[i] == "ABSTAINED" or i in h for i in ids)}
        out["arms"][arm] = o; print(arm, json.dumps(o))
    U = {arm: out["arms"][arm]["U"] for arm in ARMS}
    s = {arm: U[arm]["declined_strict"] for arm in ARMS}; sft, dpo, rl = ARMS
    out["strict_predictions"] = {"P1": abs(s[rl] - s[dpo]) <= 5, "P2": s[dpo] < s[sft]}
    print("strict reading, invented declined:", s, "-> P1", "holds" if out["strict_predictions"]["P1"] else "flips to FAIL",
          "| P2", "holds" if out["strict_predictions"]["P2"] else "still fails")
    json.dump(out, open(a.out, "w"), indent=1)
if __name__ == "__main__":
    main()
