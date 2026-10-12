#!/usr/bin/env python3
"""Score the blind Turbo-Brilliance pelican panel exactly as the prereg's "Scoring" section registers it.
Run from this directory: python3 score_panel.py [ratings_<rater>.json ...] (default: every ratings_*.json).

Pooled: each pair's mode-side rate averaged over raters (can't decide = 0.5); > 0.5 mode, < 0.5 CTRL,
exactly 0.5 excluded. Unshown pairs (a side with no drawing) count for the side that has one, for every
rater. H-1: exact two-sided sign test over the pooled pairs. Guesses scored per rater, split by whether the
pair's CTRL drawing had already appeared earlier in the page order (the recurrence tell, Addendum 1)."""
import glob, hashlib, json, sys
from math import comb

SEALED = "d77a2f10773a97508dd4068bfa86ebe49912056ed2f1a76311f58249afa92fed"


def sign_p(k, n):
    """Exact two-sided sign test, p = 0.5."""
    if n == 0:
        return 1.0
    lo = min(k, n - k)
    return min(1.0, 2 * sum(comb(n, i) for i in range(lo + 1)) / 2 ** n)


raw = open("MAPPING_SEALED.json", "rb").read()
assert hashlib.sha256(raw).hexdigest() == SEALED, "mapping does not match the sealed hash"
M = json.loads(raw)
arm_of = {code: d["arm"] for code, d in M["drawings"].items()}
pairs = {p["id"]: p for p in M["pairs"]}
order = [p["id"] for p in M["pairs"]]  # page order

seen, first_sight = set(), {}
for pid in order:
    ctrl = next(c for c in pairs[pid]["pair"] if arm_of[c] == "CTRL")
    first_sight[pid] = ctrl not in seen
    seen.add(ctrl)

files = sys.argv[1:] or sorted(glob.glob("ratings_*.json"))
pooled = {pid: [] for pid in order}
report = {"raters": {}, "unshown": M["unshown"]}
for f in files:
    R = json.load(open(f))
    rater = R["rater"]
    wins = {"mode": 0, "ctrl": 0, "tie": 0}
    guess = {"first": [0, 0], "repeat": [0, 0], "none": 0}
    per_pair = []
    for row in R["picks"]:
        pid = row["pair"]
        p = pairs[pid]
        side = {"a": row["a"], "b": row["b"]}
        assert [row["a"], row["b"]] == p["pair"], f"{pid}: page sides differ from the sealed mapping"
        if row["pref"] == "tie":
            rate, w = 0.5, "tie"
        else:
            w = "mode" if arm_of[side[row["pref"]]] != "CTRL" else "ctrl"
            rate = 1.0 if w == "mode" else 0.0
        wins[w] += 1
        pooled[pid].append(rate)
        g = None
        if row["guess"] in ("a", "b"):
            g = arm_of[side[row["guess"]]] != "CTRL"
            k = "first" if first_sight[pid] else "repeat"
            guess[k][0] += g
            guess[k][1] += 1
        else:
            guess["none"] += 1
        per_pair.append({"pair": pid, "mode": p["mode"], "rep": p["rep"], "winner": w, "guess_right": g,
                         "ctrl_first_sight": first_sight[pid], "ms": row["ms"]})
    unshown = len(M["unshown"])
    right = guess["first"][0] + guess["repeat"][0]
    n_g = guess["first"][1] + guess["repeat"][1]
    report["raters"][rater] = {
        "shown": wins, "unshown_ctrl_wins": unshown,
        "decisive_with_unshown": {"mode": wins["mode"], "ctrl": wins["ctrl"] + unshown},
        "sign_p_with_unshown": sign_p(wins["mode"], wins["mode"] + wins["ctrl"] + unshown),
        "guesses": guess, "guess_right": right, "guess_n": n_g,
        "guess_one_sided_p": sum(comb(n_g, i) for i in range(right, n_g + 1)) / 2 ** n_g if n_g else None,
        "per_pair": per_pair,
    }

mode_n = ctrl_n = excl = 0
by_mode = {}
for pid in order:
    rates = pooled[pid]
    if not rates:
        continue
    avg = sum(rates) / len(rates)
    m = pairs[pid]["mode"]
    by_mode.setdefault(m, {"mode": 0, "ctrl": 0, "excluded": 0})
    if avg > 0.5:
        mode_n += 1; by_mode[m]["mode"] += 1
    elif avg < 0.5:
        ctrl_n += 1; by_mode[m]["ctrl"] += 1
    else:
        excl += 1; by_mode[m]["excluded"] += 1
for u in M["unshown"]:  # missing-drawing rule: a win for the side with a drawing, for every rater
    ctrl_n += 1
    by_mode.setdefault(u["mode"], {"mode": 0, "ctrl": 0, "excluded": 0})["ctrl"] += 1
report["pooled"] = {"raters": list(report["raters"]), "mode": mode_n, "ctrl": ctrl_n, "excluded_0.5": excl,
                    "sign_p_two_sided": sign_p(mode_n, mode_n + ctrl_n), "by_mode": by_mode}
json.dump(report, open("panel_score.json", "w"), indent=1)
print(json.dumps({k: v for k, v in report.items() if k != "raters"}, indent=1))
for r, v in report["raters"].items():
    print(r, {k: v[k] for k in v if k != "per_pair"})
