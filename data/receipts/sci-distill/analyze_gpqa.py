#!/usr/bin/env python3
"""PREREG_SCI_DISTILL.md GPQA analysis, on the public (text-free) rows only.
Rounds used: those complete (all 198 items) in BOTH arms. Per item, accuracy = mean over those rounds. Primary: paired
difference B - A of mean accuracy over items, 95 % percentile bootstrap over items (10,000 resamples, seed 20261109);
truncated or unanswered = wrong. Sensitivity: the same on items never truncated in either arm. Also per arm: truncation
and no-answer rates, median completion tokens per request, tokens per correct answer (sum tokens / sum correct), and
per-domain accuracy (descriptive).
Usage: analyze_gpqa.py A_FILE B_FILE [--json OUT]"""
import argparse, json, random, statistics
from collections import defaultdict


def load(path):
    rows = [json.loads(l) for l in open(path)]
    return rows[0]["arm"], [r for r in rows[1:] if not r.get("header")]


def by_round(rows):
    d = defaultdict(dict)
    for r in rows:
        d[r["round"]][r["id"]] = r
    return d


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("A"); ap.add_argument("B"); ap.add_argument("--json")
    ap.add_argument("--field", default="correct", help="correct (registered) or correct_any (Deviation 1, regraded files)")
    a = ap.parse_args()
    (na, ra), (nb, rb) = load(a.A), load(a.B)
    A, B = by_round(ra), by_round(rb)
    rounds = sorted(r for r in set(A) & set(B) if len(A[r]) == 198 and len(B[r]) == 198)
    ids = sorted(A[rounds[0]]) if rounds else []
    out = {"arms": [na, nb], "grade": a.field, "rounds": rounds, "n_items": len(ids)}
    if len(rounds) < 2:
        out["status"] = f"INCOMPLETE: {len(rounds)} complete round(s), the prereg needs 2"
    trunc = lambda r: r["finish"] == "length"
    acc = lambda D, i: sum(D[k][i][a.field] for k in rounds) / len(rounds)

    def paired(keep):
        diffs = [acc(B, i) - acc(A, i) for i in keep]
        rng = random.Random(20261109); boot = []
        for _ in range(10000):
            s = [diffs[rng.randrange(len(diffs))] for _ in diffs]; boot.append(sum(s) / len(s))
        boot.sort()
        return {"n_items": len(keep), na: round(statistics.mean(acc(A, i) for i in keep), 4),
                nb: round(statistics.mean(acc(B, i) for i in keep), 4), "diff": round(sum(diffs) / len(diffs), 4),
                "ci95": [round(boot[249], 4), round(boot[9749], 4)]}

    if rounds:
        out["primary"] = paired(ids)
        clean = [i for i in ids if not any(trunc(D[k][i]) for D in (A, B) for k in rounds)]
        out["sensitivity_never_truncated"] = paired(clean)
        for name, D in ((na, A), (nb, B)):
            rs = [D[k][i] for k in rounds for i in ids]
            tok = sum(r["completion_tokens"] or 0 for r in rs); cor = sum(r[a.field] for r in rs)
            dom = defaultdict(list)
            for r in rs: dom[r["domain"]].append(r[a.field])
            out[name] = {"requests": len(rs), "accuracy": round(cor / len(rs), 4),
                         "truncated": round(sum(trunc(r) for r in rs) / len(rs), 4),
                         "no_answer": round(sum((r.get("answer_form") == "none") if a.field == "correct_any" else (not r["answered"]) for r in rs) / len(rs), 4),
                         "bare_letter_answers": round(sum(r.get("answer_form") == "bare_letter" for r in rs) / len(rs), 4),
                         "median_completion_tokens": statistics.median(r["completion_tokens"] or 0 for r in rs),
                         "mean_completion_tokens": round(tok / len(rs)), "tokens_per_correct": round(tok / max(cor, 1)),
                         "by_domain": {k: round(sum(v) / len(v), 3) for k, v in sorted(dom.items())}}
        out["token_ratio_median_B_over_A"] = round(out[nb]["median_completion_tokens"] / max(out[na]["median_completion_tokens"], 1), 3)
    print(json.dumps(out, indent=1))
    if a.json:
        json.dump(out, open(a.json, "w"), indent=1)


if __name__ == "__main__":
    main()
