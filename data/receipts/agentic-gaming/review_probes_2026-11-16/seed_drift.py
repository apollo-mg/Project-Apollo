"""Probe from the fresh-context review of DESIGN_v1 (REVIEW_2026-11-16.md), kept as the reviewer wrote it except
for paths: the repository root is derived from this file and the scratch directory is argv[1].
Pilot raw logs: near-repeat runs, and where two seeds of one cell first differ in calls and in tool OUTPUT.
No arguments.
"""
import json, re, difflib, itertools
from pathlib import Path
RAW = Path(__file__).resolve().parents[1] / "pilot" / "raw"
def load(arm, name): return json.load(open(RAW / arm / f"{name}.json"))
def sig(e): return (e["tool"], json.dumps(e.get("args", {}), sort_keys=True))
def out(e): return e.get("out", "") + "|" + e.get("err", "") + f"|{e.get('rc')}"
# near-repeat rule: longest run of consecutive calls with same tool and SequenceMatcher ratio >= 0.9 vs previous call
def near_run(d, thr=0.9):
    L = d["log"]; best = cur = 0; at = None
    for i in range(1, len(L)):
        a, b = sig(L[i-1]), sig(L[i])
        ok = a[0] == b[0] and b[0] != "finish" and difflib.SequenceMatcher(None, a[1], b[1], autojunk=False).ratio() >= thr
        cur = cur + 1 if ok else 0
        if cur > best: best, at = cur, i
    return best, at
print("== near-repeat run (consecutive calls >=0.9 similar to the previous one), all 51 ==")
rows = []
for f in sorted(RAW.glob("*/*.json")):
    d = json.load(open(f)); rows.append((d["report"] is None, near_run(d)[0], d["arm"], d["name"]))
for noexit in (True, False):
    xs = sorted([r[1] for r in rows if r[0] == noexit])
    print(("no-exit" if noexit else "exited "), "n =", len(xs), "longest near-repeat runs:", xs)
print("\n== drift between seeds of the same F2 cell ==")
for arm in ("BASE", "ARE", "QWC"):
    for rung in ("easy", "hard", "impossible"):
        eps = [load(arm, f"F2_{rung}_s{s}") for s in (1, 2, 3)]
        for (i, a), (j, b) in itertools.combinations(enumerate(eps, 1), 2):
            n = min(len(a["log"]), len(b["log"]))
            fc = next((k for k in range(n) if sig(a["log"][k]) != sig(b["log"][k])), None)
            fo = next((k for k in range(n) if out(a["log"][k]) != out(b["log"][k])), None)
            desc = ""
            if fo is not None:
                ea, eb = a["log"][fo], b["log"][fo]
                dl = [l for l in difflib.unified_diff(out(ea).splitlines(), out(eb).splitlines(), lineterm="", n=0) if l[:1] in "+-" and l[:3] not in ("+++", "---")]
                desc = f"{ea['tool']} {json.dumps(ea['args'])[:50]} :: {dl[0][:70] if dl else ''} / {dl[len(dl)//2][:70] if dl else ''}"
            print(f"{arm} {rung} s{i} vs s{j}: first differing call at step {fc}; first differing output at step {fo}: {desc}")
