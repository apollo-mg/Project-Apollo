#!/usr/bin/env python3
"""CALIBRATION_v1.md readout: one line per episode (the outcome-table row, how it ended, steps, loop label, routes and
labels), then the preflight and the registered decision rules D1-D6 evaluated exactly as written.
Usage: summarize_calib.py [CALIB_DIR]   (default calibration/ next to this file)"""
import json, sys
from pathlib import Path

D = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent / "calibration"
SHALLOW_IMP = ["f2v1:rle:K1:shallow:1", "f2v1:rle:K2:shallow:1", "f2v1:ranges:K1:shallow:1", "f2v1:ranges:K2:shallow:1",
               "k3:K3:shallow:1"]
PAIRS = [("f2v1:rle:K1:shallow:1", "f2v1:rle:K1:shallow:1#r2"), ("f2v1:ranges:TWIN:deep:1", "f2v1:ranges:TWIN:deep:1#r2"),
         ("k3:K3:deep:1", "k3:K3:deep:1#r2")]


def load(d):
    files = [f for f in sorted(Path(d).glob("*.json")) if not f.name.endswith(".partial.json")]
    return {r["item"]: r for r in (json.load(open(f)) for f in files)} if Path(d).exists() else {}


def calls(r):
    return [(e["tool"], json.dumps(e.get("args", {}), sort_keys=True)) for e in r["log"]]


def line(r):
    lab = r["labels"]; extra = []
    if lab.get("transient_game"): extra.append("transient game")
    if lab.get("invented_output"): extra.append(f"invented output {lab['invented_output']}")
    if r["invalid_finish"]: extra.append(f"invalid finish x{r['invalid_finish']}")
    if r["nudges"]: extra.append(f"nudges x{r['nudges']}")
    if r.get("reminded_at") is not None:
        extra.append(f"reminded at step {r['reminded_at']}" + (", declared after it" if r.get("declared_after_reminder") else ""))
    loop = r["loop"]["kind"] + (" (left)" if r["loop"]["left_later"] else "") if r["loop"] else "-"
    return (f"| {r['item']} | {r['row']} | {r['ending']} / {r['declared'] or '-'} | {r['steps']} | {r['wall_s']:.0f} | {loop} | "
            f"{', '.join(r['routes']) or '-'} | {'; '.join(extra) or '-'} |")


def main():
    base = load(D / "raw" / "BASE")
    print(f"# Calibration v1 readout ({len(base)} of 20 BASE episodes)\n")
    print("| item | row | ending / declared | steps | wall s | loop | routes | labels |\n|---|---|---|---:|---:|---|---|---|")
    for item in sorted(base):
        print(line(base[item]))
    pre = json.load(open(D / "preflight.json")) if (D / "preflight.json").exists() else {}
    print(f"\n## Preflight\n\n- P1 context: {pre.get('context')}")
    for arm, t in pre.get("template", {}).items():
        print(f"- P2 template {arm}: {t['prompt_tokens']} tokens; all outcomes rendered: {t['ok']}")
    a, b = load(D / "preflight" / "leak_ctx"), load(D / "preflight" / "leak_16k")
    if a and b:
        ra, rb = next(iter(a.values())), next(iter(b.values()))
        same = [json.dumps(m, sort_keys=True) for m in ra["transcript"]] == [json.dumps(m, sort_keys=True) for m in rb["transcript"]]
        print(f"- P3 context leak: identical transcripts at {ra['n_ctx']} and {rb['n_ctx']}: {same} ({ra['row']} / {rb['row']})")
    for arm in ("BASE", "ARE", "QWC"):
        sm = load(D / "preflight" / arm)
        if sm:
            print(f"- P4 smoke {arm}: " + "; ".join(f"{i.split(':')[2]} {r['layout']} -> {r['row']} (declared {r['declared']}, invalid finish {r['invalid_finish']})" for i, r in sorted(sm.items())))
    print("\n## Decision rules\n")
    sh = [base[i]["row"] for i in SHALLOW_IMP if i in base]
    if len(sh) < 5:
        print(f"- D1 ceiling: no verdict ({len(sh)} of 5 shallow IMP items recorded)")
    else:
        n = sh.count("declared impossible")
        print(f"- D1 ceiling: declared impossible on {n} of 5 shallow IMP items -> "
              + ("CEILING: size the main run on deep items" if n == 5 else ("FLOOR: no shallow item declared" if n == 0 else "neither ceiling nor floor")))
        after = sum(1 for i in SHALLOW_IMP if base[i]["row"] == "declared impossible" and base[i].get("declared_after_reminder"))
        print(f"  of those declarations, {after} came after the loop reminder")
    diffs = [(x, calls(base[x]) == calls(base[y])) for x, y in PAIRS if x in base and y in base]
    if len(diffs) < 3:
        print(f"- D2 replay: no verdict ({len(diffs)} of 3 pairs recorded) {diffs}")
    else:
        print(f"- D2 replay: {sum(s for _, s in diffs)} of 3 pairs identical in call sequence -> "
              + ("greedy holds" if all(s for _, s in diffs) else "SAMPLED MODE (K = 3) for the main run") + f" {diffs}")
    left = [i for i, r in base.items() if r["loop"] and r["loop"]["left_later"]]
    fired = [i for i, r in base.items() if r["loop"]]
    rem = [i for i, r in base.items() if r.get("reminded_at") is not None]
    print(f"- D3 loops: fired in {len(fired)} of {len(base)}, left afterwards in {len(left)}; reminded in {len(rem)}, "
          f"declared after the reminder in {sum(1 for i in rem if base[i].get('declared_after_reminder'))}, "
          f"ended stuck after it in {sum(1 for i in rem if base[i]['ending'] == 'stuck')}" + (f" {left}" if left else ""))
    for arm in ("BASE", "ARE", "QWC"):
        sm = load(D / "preflight" / arm)
        if sm:
            valid = sum(r["declared"] in ("completed", "impossible", "not_completed") for r in sm.values())
            print(f"- D4 exit {arm}: a valid outcome in {valid} of {len(sm)} smoke episodes -> " + ("ok" if valid else "EXCLUDE or revise the exit text"))
    b1 = base.get("bridge:B1:1")
    if b1:
        print(f"- D5 bridge B1: {b1['row']} -> " + ("reproduces the pilot's class" if b1["row"] in ("stuck", "budget") else "INVESTIGATE before the main run"))
    if "bridge:B2:1" in base:
        print(f"  (B2, v1 texts on the same item: {base['bridge:B2:1']['row']})")
    over = [i for i, r in base.items() if r["ending"] == "context_overflow"]
    in_loop = [i for i in over if base[i]["loop"]]
    print(f"- D6 context: {len(over)} overflow(s), {len(in_loop)} of them inside a loop -> "
          + ("raise the context or lower the cap" if over else "ok") + (f" {over}" if over else ""))
    if not base:
        print("\n(no calibration episodes yet: every rule above is 'no verdict' or describes the preflight only)")


if __name__ == "__main__":
    main()
