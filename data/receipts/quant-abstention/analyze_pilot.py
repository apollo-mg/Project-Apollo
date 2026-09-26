#!/usr/bin/env python3
"""Score the pilot against PREREG_PILOT.md (P1-P4 decisions, Q1-Q4 predictions) and Deviations 1-3.

Graded items only: TRUNCATED / NO-ANSWER / INVALID are excluded from every rate and counted separately (Dev. 3).
Strict grade gates everything; the lenient year grade and the prose-refusal flag are descriptive (Dev. 2, 3).
Bootstrap: 10,000 paired resamples over items (seed fixed), percentile 95 % CIs.
Writes RESULT_pilot.json.
"""
import json, random
from pathlib import Path

HERE = Path(__file__).resolve().parent
ARMS = ["C", "M", "L", "B"]
GRADED = {"CORRECT", "WRONG", "ABSTAINED"}
B = 10_000
rng = random.Random(20260926)


def load(arm):
    rows = [json.loads(l) for l in open(HERE / "raw" / f"pilot_{arm}.jsonl")]
    return rows[0], {r["id"]: r for r in rows[1:]}


def rate(xs):
    return sum(xs) / len(xs) if xs else float("nan")


def auroc(pos, neg):
    """P(score_pos > score_neg) + 0.5 P(tie): U items are the positives."""
    if not pos or not neg:
        return float("nan")
    s = sum((p > n) + 0.5 * (p == n) for p in pos for n in neg)
    return s / (len(pos) * len(neg))


def ci(stat, ids):
    vals = sorted(stat([rng.choice(ids) for _ in ids]) for _ in range(B))
    return vals[int(0.025 * B)], vals[int(0.975 * B) - 1]


def main():
    D = {a: load(a) for a in ARMS if (HERE / "raw" / f"pilot_{a}.jsonl").exists()}
    out = {"arms": {}, "decisions": {}, "predictions": {}}
    for a, (hdr, R) in D.items():
        g = {i: r for i, r in R.items() if r["grade"] in GRADED}
        by = lambda arm: [r for r in g.values() if r["arm"] == arm]
        ans = by("E") + by("H")
        out["arms"][a] = {
            "model": hdr["meta"].get("model"), "sha256": hdr["meta"].get("sha256"), "n_rows": len(R),
            "not_graded": {k: sum(r["grade"] == k for r in R.values()) for k in ("TRUNCATED", "NO-ANSWER", "INVALID")},
            "multi_answer_lines": sum(r["n_answer_lines"] > 1 for r in R.values()),
            # P1: R-slot vs R-gen agreement
            "P1_agreement": rate([(r["P_abs"] > 0.5) == (r["grade"] == "ABSTAINED") for r in g.values()]),
            "knowledge_E": rate([r["grade"] == "CORRECT" for r in by("E")]),
            "knowledge_H": rate([r["grade"] == "CORRECT" for r in by("H")]),
            "knowledge_H_lenient": rate([r["grade_lenient"] == "CORRECT" for r in by("H")]),
            "knowledge_E_lenient": rate([r["grade_lenient"] == "CORRECT" for r in by("E")]),
            "abstain_U": rate([r["grade"] == "ABSTAINED" for r in by("U")]),
            "confab_U_gen": rate([r["grade"] == "WRONG" for r in by("U")]),
            "prose_refusal_U": sum(r["prose_refusal"] for r in by("U")),
            "overabstain_E": rate([r["grade"] == "ABSTAINED" for r in by("E")]),
            "overabstain_H": rate([r["grade"] == "ABSTAINED" for r in by("H")]),
            # AFM-22 split, R-slot (all rows with a slot read, graded or not: R-slot needs no generation)
            "timidity_E": rate([r["P_abs"] for r in R.values() if r["arm"] == "E"]),
            "timidity_H": rate([r["P_abs"] for r in R.values() if r["arm"] == "H"]),
            "confab_U_slot": rate([1 - r["P_abs"] for r in R.values() if r["arm"] == "U"]),
            "AUROC_U_vs_EH": auroc([r["P_abs"] for r in R.values() if r["arm"] == "U"],
                                   [r["P_abs"] for r in R.values() if r["arm"] in "EH"]),
        }
    A = out["arms"]
    # P1 decision
    ok = {a: A[a]["P1_agreement"] >= 0.85 for a in A}
    out["decisions"]["P1"] = {"agreement": {a: round(A[a]["P1_agreement"], 3) for a in A}, "pass_by_arm": ok,
                              "R_slot_primary": all(ok.values()) and len(ok) == 4}
    # P2 and P4: paired differences vs C over items graded in both arms
    if "C" in D:
        RC = D["C"][1]
        p2 = {}
        for a in ("L", "B", "M"):
            if a not in D:
                continue
            Ra = D[a][1]
            both = [i for i in RC if i in Ra and RC[i]["grade"] in GRADED and Ra[i]["grade"] in GRADED]
            H = [i for i in both if RC[i]["arm"] == "H"]
            U = [i for i in both if RC[i]["arm"] == "U"]
            dH = lambda ids: rate([Ra[i]["grade"] == "CORRECT" for i in ids]) - rate([RC[i]["grade"] == "CORRECT" for i in ids])
            dU = lambda ids: rate([Ra[i]["grade"] == "ABSTAINED" for i in ids]) - rate([RC[i]["grade"] == "ABSTAINED" for i in ids])
            p2[a] = {"H_correct_diff": round(dH(H), 3), "H_correct_ci": [round(x, 3) for x in ci(dH, H)], "n_H": len(H),
                     "U_abstain_diff": round(dU(U), 3), "U_abstain_ci": [round(x, 3) for x in ci(dU, U)], "n_U": len(U)}
            p2[a]["differs"] = not (p2[a]["H_correct_ci"][0] <= 0 <= p2[a]["H_correct_ci"][1]) or \
                               not (p2[a]["U_abstain_ci"][0] <= 0 <= p2[a]["U_abstain_ci"][1])
            if a == "L":   # P4 sizing inputs, C vs L
                allb = both
                disc_abs = rate([(RC[i]["grade"] == "ABSTAINED") != (Ra[i]["grade"] == "ABSTAINED") for i in allb])
                ansb = [i for i in allb if RC[i]["arm"] != "U"]
                disc_cor = rate([(RC[i]["grade"] == "CORRECT") != (Ra[i]["grade"] == "CORRECT") for i in ansb])
                d = [Ra[i]["P_abs"] - RC[i]["P_abs"] for i in RC if i in Ra]
                m = sum(d) / len(d)
                sd = (sum((x - m) ** 2 for x in d) / (len(d) - 1)) ** 0.5
                out["decisions"]["P4"] = {"discordance_abstained_all": round(disc_abs, 3), "n_all": len(allb),
                                          "discordance_correct_answerable": round(disc_cor, 3), "n_answerable": len(ansb),
                                          "R_slot_paired_diff_mean": round(m, 4), "R_slot_paired_diff_sd": round(sd, 4),
                                          "n_slot": len(d)}
        out["decisions"]["P2"] = {"by_arm": p2, "thinking_off_carries":
                                  any(p2[a]["differs"] for a in ("L", "B") if a in p2)}
        # P3: corpus range at C
        out["decisions"]["P3"] = {"E_correct": round(A["C"]["knowledge_E"], 3), "E_pass": A["C"]["knowledge_E"] >= 0.85,
                                  "H_correct": round(A["C"]["knowledge_H"], 3),
                                  "H_pass": 0.25 <= A["C"]["knowledge_H"] <= 0.75}
        # predictions
        P = out["predictions"]
        P["Q1"] = all(A[a]["P1_agreement"] >= 0.85 for a in ("C", "M") if a in A)
        if "L" in A:
            P["Q2"] = {"H_correct_lower": A["L"]["knowledge_H"] < A["C"]["knowledge_H"],
                       "P_abs_answerable_higher": (A["L"]["timidity_E"] + A["L"]["timidity_H"]) >
                                                   (A["C"]["timidity_E"] + A["C"]["timidity_H"])}
        if "B" in A:
            P["Q3"] = {"U_abstain_lower": A["B"]["abstain_U"] < A["C"]["abstain_U"],
                       "P_abs_answerable_not_higher": (A["B"]["timidity_E"] + A["B"]["timidity_H"]) <=
                                                       (A["C"]["timidity_E"] + A["C"]["timidity_H"])}
        P["Q4"] = A["C"]["AUROC_U_vs_EH"] >= 0.85
    # ---- DESCRIPTIVE (not gates): what the registered numbers rest on --------------------------------------------
    T = ("capital", "novel", "opera", "university")
    desc = out["descriptive"] = {}
    for a, (hdr, R) in D.items():
        g = [r for r in R.values() if r["grade"] in GRADED]
        tab = {f"slot_{s}_gen_{t}": sum(((r["P_abs"] > 0.5) == s) and ((r["grade"] == "ABSTAINED") == t) for r in g)
               for s in (True, False) for t in (True, False)}
        wt = {tp: auroc([r["P_abs"] for r in R.values() if r["arm"] == "U" and r["template"] == tp],
                        [r["P_abs"] for r in R.values() if r["arm"] in "EH" and r["template"] == tp]) for tp in T}
        n = len(g); st = tab["slot_True_gen_True"] + tab["slot_True_gen_False"]; gt = tab["slot_True_gen_True"] + tab["slot_False_gen_True"]
        po = (tab["slot_True_gen_True"] + tab["slot_False_gen_False"]) / n; pe = (st * gt + (n - st) * (n - gt)) / n ** 2
        desc[a] = {"P1_2x2": tab, "P1_baseline_never_abstain": round(rate([r["grade"] != "ABSTAINED" for r in g]), 3),
                   "P1_kappa": round((po - pe) / (1 - pe), 3),
                   "not_graded_slot": [(r["id"], round(r["P_abs"], 3)) for r in R.values() if r["grade"] not in GRADED],
                   "AUROC_within_template": {k: round(v, 3) for k, v in wt.items()},
                   "AUROC_within_template_mean": round(sum(wt.values()) / len(wt), 3),
                   "knowledge_E_lenient": round(A[a]["knowledge_E_lenient"], 3),
                   "knowledge_H_lenient": round(A[a]["knowledge_H_lenient"], 3),
                   "U_abstain_by_template": {tp: f"{sum(r['grade'] == 'ABSTAINED' for r in g if r['arm'] == 'U' and r['template'] == tp)}/"
                                                 f"{sum(1 for r in g if r['arm'] == 'U' and r['template'] == tp)}" for tp in T},
                   "H_correct_by_template": {tp: f"{sum(r['grade'] == 'CORRECT' for r in g if r['arm'] == 'H' and r['template'] == tp)}/"
                                                 f"{sum(1 for r in g if r['arm'] == 'H' and r['template'] == tp)}" for tp in T}}
    if "C" in D:
        RC = D["C"][1]
        for a in ("M", "L", "B"):
            if a not in D:
                continue
            Ra = D[a][1]
            both = [i for i in RC if i in Ra and RC[i]["grade"] in GRADED and Ra[i]["grade"] in GRADED]
            sgn = lambda arm, k: {"arm_only": sum(Ra[i]["grade"] == k and RC[i]["grade"] != k for i in both if RC[i]["arm"] == arm),
                                  "C_only": sum(RC[i]["grade"] == k and Ra[i]["grade"] != k for i in both if RC[i]["arm"] == arm)}
            desc[a]["discordant_vs_C"] = {"H_correct": sgn("H", "CORRECT"), "U_abstained": sgn("U", "ABSTAINED")}
    json.dump(out, open(HERE / "RESULT_pilot.json", "w"), indent=1)
    print(json.dumps(desc, indent=1))
    cols = ["P1_agreement", "knowledge_E", "knowledge_H", "abstain_U", "confab_U_gen", "overabstain_E", "overabstain_H",
            "timidity_E", "timidity_H", "confab_U_slot", "AUROC_U_vs_EH"]
    print("arm  " + "  ".join(f"{c[:13]:>13s}" for c in cols))
    for a in A:
        print(f"{a:4s} " + "  ".join(f"{A[a][c]:13.3f}" for c in cols), " not graded:", A[a]["not_graded"],
              " prose U:", A[a]["prose_refusal_U"])
    print(json.dumps(out["decisions"], indent=1))
    print(json.dumps(out["predictions"], indent=1))


if __name__ == "__main__":
    main()
