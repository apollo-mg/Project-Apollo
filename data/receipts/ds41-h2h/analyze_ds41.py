#!/usr/bin/env python3
"""PREREG_DS41_H2H.md analysis. Committed and self-tested on stored Flash-Next arms before any DS41 row existed.
Per arm (M1, as RESULT_FLASHNEXT.md): E and H accuracy (CORRECT), H abstained, U refused (ABSTAINED; lenient also counts
a bare UNKNOWN graded NO-ANSWER), U confabulated (WRONG), unfinished (TRUNCATED, or INVALID at finish=length).
Paired A - B on the same items: difference, 95 % percentile bootstrap over items (10,000 resamples, seed 20261103),
exact two-sided McNemar on the discordant pairs, and grade agreement. Replay: byte identity of `content` between an arm
and its replay on the replay's items.
Usage: analyze_ds41.py A B [--replay A_REPLAY_FILE] [--json OUT]   (A, B = arm names under quant-abstention/raw)"""
import argparse, json, math, random, re
from pathlib import Path

RAW = Path(__file__).resolve().parent.parent / "quant-abstention" / "raw"
bare = lambda r: r.get("grade") == "NO-ANSWER" and re.fullmatch(r"\W*unknown\W*", (r.get("content") or "").strip(), re.I) is not None
unf = lambda r: r["grade"] == "TRUNCATED" or (r["grade"] == "INVALID" and r.get("finish") == "length")
METRICS = {   # name: (item group, predicate)
    "E_correct": ("E", lambda r: r["grade"] == "CORRECT"),
    "H_correct": ("H", lambda r: r["grade"] == "CORRECT"),
    "H_abstained": ("H", lambda r: r["grade"] == "ABSTAINED"),
    "U_refused": ("U", lambda r: r["grade"] == "ABSTAINED"),
    "U_refused_lenient": ("U", lambda r: r["grade"] == "ABSTAINED" or bare(r)),
    "U_confabulated": ("U", lambda r: r["grade"] == "WRONG"),
    "unfinished": (None, unf),
}


def load(path):
    rows = [json.loads(l) for l in open(path)]
    return rows[0], {r["id"]: r for r in rows[1:] if "id" in r}


def group(i): return i.split("-")[1]


def mcnemar(b, c):
    """Exact two-sided McNemar: binomial test of b successes in b + c trials at p = 0.5."""
    n = b + c
    if n == 0: return 1.0
    k = min(b, c)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)


def paired(A, B, ids, pred, rng, n_boot=10000):
    a = [int(pred(A[i])) for i in ids]; b = [int(pred(B[i])) for i in ids]
    d = [x - y for x, y in zip(a, b)]; n = len(d)
    boots = sorted(sum(d[rng.randrange(n)] for _ in range(n)) / n for _ in range(n_boot))
    disc_a = sum(1 for x, y in zip(a, b) if x and not y); disc_b = sum(1 for x, y in zip(a, b) if y and not x)
    return {"n": n, "A": round(sum(a) / n, 4), "B": round(sum(b) / n, 4), "diff": round(sum(d) / n, 4),
            "ci95": [round(boots[int(0.025 * n_boot)], 4), round(boots[int(0.975 * n_boot) - 1], 4)],
            "only_A": disc_a, "only_B": disc_b, "mcnemar_p": round(mcnemar(disc_a, disc_b), 4)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("A"); ap.add_argument("B")
    ap.add_argument("--replay", help="raw file of A's replay (a subset of items, fresh server)")
    ap.add_argument("--json")
    a = ap.parse_args()
    (hA, A), (hB, B) = load(RAW / f"main_{a.A}.jsonl"), load(RAW / f"main_{a.B}.jsonl")
    ids = sorted(set(A) & set(B))
    if set(A) != set(B): print(f"note: items differ between arms; using the {len(ids)} shared")
    rng = random.Random(20261103)
    out = {"A": a.A, "B": a.B, "n_items": len(ids), "metrics": {}}
    for name, (g, pred) in METRICS.items():
        sub = [i for i in ids if g is None or group(i) == g]
        out["metrics"][name] = paired(A, B, sub, pred, rng)
    out["grade_agreement"] = round(sum(A[i]["grade"] == B[i]["grade"] for i in ids) / len(ids), 4)
    if a.replay:
        _, R = load(a.replay)
        rid = sorted(set(R) & set(A))
        out["replay"] = {"n": len(rid), "content_identical": sum(A[i]["content"] == R[i]["content"] for i in rid),
                         "grade_identical": sum(A[i]["grade"] == R[i]["grade"] for i in rid)}
    for k, v in out["metrics"].items():
        print(f"{k:18s} n={v['n']:3d}  {a.A} {v['A']:.3f}  {a.B} {v['B']:.3f}  diff {v['diff']:+.3f} "
              f"[{v['ci95'][0]:+.3f}, {v['ci95'][1]:+.3f}]  only {v['only_A']}/{v['only_B']}  McNemar p={v['mcnemar_p']}")
    print("grade agreement", out["grade_agreement"], "| replay", out.get("replay"))
    if a.json: json.dump(out, open(a.json, "w"), indent=1)


if __name__ == "__main__":
    main()
