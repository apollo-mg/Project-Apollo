#!/usr/bin/env python3
"""PREREG_LOOP_LOGITS.md (+ Deviation 1: full-prefill probes, raw/full_*). Scores PC, Q1-Q3 and the Q4 descriptives.
Writes RESULT_loop_logits.json and prints a summary."""
import collections, glob, json, math
from pathlib import Path

HERE = Path(__file__).resolve().parent
THINK_END = 248069
MARKERS = {i for i, _ in json.load(open(HERE.parent / "marker-penalty/marker_ids.json"))}


def load(prefix="full"):
    T = {}
    for f in sorted(glob.glob(str(HERE / f"raw/{prefix}_*.jsonl"))):
        L = [json.loads(l) for l in open(f)]
        if not L or not any(r.get("end") for r in L[1:]):
            continue                                   # incomplete trace: never scored
        T[Path(f).stem[len(prefix) + 1:]] = (L[0]["meta"], L[1:])
    return T


def pstop(r):
    return next((math.exp(t[2]) for t in r["top"] if t[0] == THINK_END), 0.0)


def top1p(r):
    return math.exp(r["top"][0][2])


def ent20(r):
    ps = [math.exp(t[2]) for t in r["top"]]; s = sum(ps)
    return -sum(p / s * math.log(p / s) for p in ps if p > 0)


def main(prefix="full"):
    T = load(prefix)
    out = {"traces": {}, "prefix": prefix}
    for name, (m, rows) in T.items():
        b = [r for r in rows if not r["end"]]
        e = [r for r in rows if r["end"]][0]
        ps = [pstop(r) for r in b]
        n = m["n_total"] - m["n_prompt"]
        third = lambda k: [pstop(r) for r in b if k * n / 3 <= r["trace_pos"] < (k + 1) * n / 3]
        early = [r for r in b if r["trace_pos"] < 3000]
        srt = sorted(b, key=lambda r: -pstop(r))[:5]
        out["traces"][name] = {
            "set": m["set"], "status": m["status"], "tokens": n, "boundaries": len(b),
            "end_pstop": pstop(e), "end_in_top20": any(t[0] == THINK_END for t in e["top"]),
            "median_boundary_pstop": sorted(ps)[len(ps) // 2] if ps else None,
            "max_boundary_pstop": max(ps) if ps else None,
            "n_boundaries_pstop_ge_0.10": sum(p >= 0.10 for p in ps),
            "mean_pstop_thirds": [sum(x) / len(x) if x else None for x in (third(0), third(1), third(2))],
            "marker_next_frac": sum(r["next_id"] in MARKERS for r in b) / len(b) if b else None,
            "first3000": {"n": len(early), "max_pstop": max((pstop(r) for r in early), default=None),
                          "mean_top1p": sum(top1p(r) for r in early) / len(early) if early else None,
                          "mean_ent20": sum(ent20(r) for r in early) / len(early) if early else None},
            "highest_pstop_boundaries": [{"trace_pos": r["trace_pos"], "pstop": round(pstop(r), 4),
                                          "next": r["next_piece"], "next_p": round(math.exp(r["true_lp"]), 4),
                                          "top3": [(t[1], round(math.exp(t[2]), 3)) for t in r["top"][:3]]} for r in srt],
            "trajectory": [(r["trace_pos"], round(pstop(r), 5)) for r in b],
        }
    X = out["traces"]
    term = {k: v for k, v in X.items() if v["status"] != "NO-STOP/REC"}
    out["PC"] = {"n_terminating": len(term),
                 "pass": sum(v["end_in_top20"] and v["end_pstop"] > (v["median_boundary_pstop"] or 0) for v in term.values()),
                 "failures": [k for k, v in term.items() if not (v["end_in_top20"] and v["end_pstop"] > (v["median_boundary_pstop"] or 0))]}
    loops = {k: v for k, v in X.items() if v["set"] == "LOOP"}
    if loops:
        out["Q1"] = {k: v["n_boundaries_pstop_ge_0.10"] for k, v in loops.items()}
        out["Q1"]["held"] = all(v["n_boundaries_pstop_ge_0.10"] >= 1 for v in loops.values())
        out["Q2"] = {k: v["mean_pstop_thirds"] for k, v in loops.items()}
        out["Q2"]["held"] = all(v["mean_pstop_thirds"][2] is not None and v["mean_pstop_thirds"][0] is not None
                                and v["mean_pstop_thirds"][2] < v["mean_pstop_thirds"][0] for v in loops.values())
        nb = sum(v["boundaries"] for v in loops.values())
        mk = sum(v["marker_next_frac"] * v["boundaries"] for v in loops.values())
        out["Q3"] = {"marker_next_frac_pooled": mk / nb, "held": mk / nb < 0.30}
    lex = collections.defaultdict(collections.Counter)   # next-token lexicon at boundaries, per set
    for name, (m, rows) in T.items():
        for r in rows:
            if not r["end"]:
                lex[m["set"]][r["next_piece"].strip() or repr(r["next_piece"])] += 1
    out["lexicon_top20"] = {s: c.most_common(20) for s, c in lex.items()}
    (HERE / f"RESULT_loop_logits{'' if prefix == 'full' else '_' + prefix}.json").write_text(json.dumps(out, indent=1))
    for k, v in sorted(X.items(), key=lambda kv: (kv[1]["set"], kv[0])):
        f3 = v["first3000"]
        print(f"{k:24s} {v['status']:16s} tok {v['tokens']:6d} bnd {v['boundaries']:4d} end P(stop) {v['end_pstop']:.3f} "
              f"med {v['median_boundary_pstop'] or 0:.4f} max {v['max_boundary_pstop'] or 0:.3f} >=.10: {v['n_boundaries_pstop_ge_0.10']:3d} "
              f"thirds {[round(x, 4) if x is not None else None for x in v['mean_pstop_thirds']]} "
              f"mk {v['marker_next_frac'] if v['marker_next_frac'] is None else round(v['marker_next_frac'], 3)} "
              f"| f3k max {f3['max_pstop'] if f3['max_pstop'] is None else round(f3['max_pstop'], 3)} "
              f"top1 {f3['mean_top1p'] if f3['mean_top1p'] is None else round(f3['mean_top1p'], 3)} "
              f"H {f3['mean_ent20'] if f3['mean_ent20'] is None else round(f3['mean_ent20'], 3)}")
    for q in ("PC", "Q1", "Q2", "Q3"):
        if q in out:
            print(q, out[q])
    for s, c in out["lexicon_top20"].items():
        print(s, c[:12])


if __name__ == "__main__":
    import sys
    main(sys.argv[1] if len(sys.argv) > 1 else "full")
