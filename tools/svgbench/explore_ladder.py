#!/usr/bin/env python3
"""EXPLORATORY ONLY -- not a pre-registered metric. Label it as such anywhere it is used.

How much does a correction change the drawing? The structural scorer saturates on competent first
drawings (both 2-bit quants' rep 1 scored 10/10 first try), so it cannot see corrections that are
purely aesthetic. This measures change magnitude between parent and child renders. It was committed
as exploratory in PREREG_BITDEPTH_FEEDBACK.md before reps 2-12, and lives in its own file so it can
never be mistaken for, or folded into, the pre-registered score_ladder.py.
"""
import sys
from pathlib import Path
import numpy as np

ROOT = Path("/mnt/TG_2TB/Projects/Apollo")
OUT = ROOT / "data/receipts/svgbench-ladder"
sys.path.insert(0, str(ROOT / "tools/svgbench"))
import svg_probe  # noqa: E402


def change(parent_png, child_png):
    mp, ap = svg_probe._ink(parent_png)
    mc, ac = svg_probe._ink(child_png)
    if mp.shape != mc.shape:
        return None
    changed = float((mp ^ mc).mean())
    union = float((mp | mc).mean()) or 1e-9
    return {"ink_px_changed": round(changed, 4),
            "changed_of_union": round(changed / union, 3),   # normalised: big drawings don't dominate
            "rgb_mean_diff": round(float(np.abs(ap - ac).mean() / 255.0), 4)}


def main():
    rows = []
    for q in ("UD-Q2_K_XL", "UD-IQ2_M", "UD-IQ4_XS", "UD-Q4_K_M"):
        for rep in (1, 2, 3):
            for child, parent in (("intent2", "p1"), ("goal2", "p1"), ("goal3", "goal2")):
                pp, cp = OUT / f"{q}_r{rep}_{parent}.png", OUT / f"{q}_r{rep}_{child}.png"
                if pp.exists() and cp.exists():
                    c = change(pp, cp)
                    if c:
                        rows.append({"quant": q, "rep": rep, "step": child, **c})
    print("EXPLORATORY -- parent->child render change magnitude (NOT pre-registered)\n")
    print(" quant        rep step      ink_px_changed  changed_of_union  rgb_mean_diff")
    for r in rows:
        print(f" {r['quant']:12s} {r['rep']}   {r['step']:8s}  {r['ink_px_changed']:>14}  "
              f"{r['changed_of_union']:>16}  {r['rgb_mean_diff']:>13}")
    for st in ("intent2", "goal2", "goal3"):
        v = [r["changed_of_union"] for r in rows if r["step"] == st]
        if v:
            print(f"\n mean changed_of_union  {st:8s} {sum(v)/len(v):.3f}   n={len(v)}")


if __name__ == "__main__":
    main()
