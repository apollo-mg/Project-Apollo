#!/usr/bin/env python3
"""Score PREREG_MARKER_PENALTY.md from raw/out_{q6k,iq3}/arm{A,B,C}_rep{1,2,3}.jsonl -> RESULT_marker.json.
M1/M3: per item, mean thinking chars over the 3 reps per arm; statistic = mean over the 16 items of log(arm / A);
ratio = exp(statistic); exact sign-flip permutation over items (2^16).
M2: answerable ANSWERED-CORRECT (of 24) and unanswerable failures = ANSWERED-WRONG or finish == 'length' (of 24).
M4 (operationalized here, the prereg says 'fall >= 90 % / at least double'): occurrences per 1,000 reasoning chars."""
import itertools, json, re
from pathlib import Path
import numpy as np

HERE = Path(__file__).parent
MODELS = {"Q6_K": "out_q6k", "IQ3_XXS": "out_iq3"}
PEN = ["Wait", "But", "Hmm", "Actually", "Alternatively", "However", "Hold", "Oh", "Maybe", "Perhaps"]
pen_re = re.compile(r"(?<![A-Za-z])(" + "|".join(PEN) + r")(?![A-Za-z])")
sub_re = re.compile(r"(?<![A-Za-z])(wait|hmm|however|alternatively|actually)(?![A-Za-z])|let me reconsider|on second thought")
SIGNS = np.array(list(itertools.product((1, -1), repeat=16)), dtype=float)

def rows(model, arm):
    out = []
    for f in sorted((HERE / "raw" / MODELS[model]).glob(f"arm{arm}_rep*.jsonl")):
        out += [json.loads(l) for l in open(f)]
    return out

def perm(d):
    d = np.asarray(d, float); return float((np.abs((SIGNS * d).mean(1)) >= abs(d.mean()) - 1e-15).mean())

R = {}
for model in MODELS:
    D = {a: rows(model, a) for a in "ABC"}
    items = sorted({r["id"] for r in D["A"]})
    assert len(items) == 16 and all(len(D[a]) == 48 for a in "ABC"), (model, [len(D[a]) for a in "ABC"])
    think = {a: {i: np.mean([len(r.get("reasoning") or "") for r in D[a] if r["id"] == i]) for i in items} for a in "ABC"}
    m = {"arms": {}}
    for a in "ABC":
        ans = [r for r in D[a] if r["id"].startswith("CAL-A")]
        una = [r for r in D[a] if r["id"].startswith("CAL-U")]
        allr = "".join(r.get("reasoning") or "" for r in D[a])
        m["arms"][a] = {
            "answerable_correct": sum(r["status"] == "ANSWERED-CORRECT" for r in ans),
            "answerable_abstained": sum(r["status"] == "ABSTAINED" for r in ans),
            "unanswerable_abstained": sum(r["status"] == "ABSTAINED" and r.get("finish") != "length" for r in una),
            "unanswerable_wrong": sum(r["status"] == "ANSWERED-WRONG" and r.get("finish") != "length" for r in una),
            "no_stop": sum(r.get("finish") == "length" for r in D[a]),
            "median_think_chars": float(np.median([len(r.get("reasoning") or "") for r in D[a]])),
            "median_think_unanswerable": float(np.median([len(r.get("reasoning") or "") for r in una])),
            "total_think_chars": len(allr),
            "penalized_per_1k": 1000 * len(pen_re.findall(allr)) / max(1, len(allr)),
            "substitutes_per_1k": 1000 * len(sub_re.findall(allr)) / max(1, len(allr)),
            "completion_tokens_total": sum(r.get("completion_tokens") or 0 for r in D[a]),
        }
        m["arms"][a]["unanswerable_fail"] = m["arms"][a]["unanswerable_wrong"] + sum(r.get("finish") == "length" for r in una)
    for a in "BC":
        d = [np.log(think[a][i] / think["A"][i]) for i in items]
        m[f"{a}_vs_A"] = {"geo_ratio": float(np.exp(np.mean(d))), "p_perm": perm(d),
                          "items_shorter": int(sum(x < 0 for x in d)),
                          "answerable_correct_delta": m["arms"][a]["answerable_correct"] - m["arms"]["A"]["answerable_correct"],
                          "unanswerable_fail_delta": m["arms"][a]["unanswerable_fail"] - m["arms"]["A"]["unanswerable_fail"]}
    R[model] = m

q, i3 = R["Q6_K"], R["IQ3_XXS"]
R["M1"] = {"ratio_C_Q6K": q["C_vs_A"]["geo_ratio"], "p": q["C_vs_A"]["p_perm"],
           "pass": q["C_vs_A"]["geo_ratio"] < 0.85 and q["C_vs_A"]["p_perm"] < 0.05}
R["M2"] = {m: {a: {"ans_ok": R[m][f"{a}_vs_A"]["answerable_correct_delta"] >= -2,
                   "una_ok": R[m][f"{a}_vs_A"]["unanswerable_fail_delta"] <= 2} for a in "BC"} for m in MODELS}
R["M2"]["pass"] = all(v["ans_ok"] and v["una_ok"] for m in MODELS for v in R["M2"][m].values())
R["M3"] = {"ratio_C_Q6K": q["C_vs_A"]["geo_ratio"], "ratio_C_IQ3": i3["C_vs_A"]["geo_ratio"],
           "diff": i3["C_vs_A"]["geo_ratio"] - q["C_vs_A"]["geo_ratio"]}
R["M3"]["pass"] = abs(R["M3"]["diff"]) <= 0.10
pa = lambda m, a, k: R[m]["arms"][a][k]
pen_A = np.mean([pa(m, "A", "penalized_per_1k") for m in MODELS]); pen_C = np.mean([pa(m, "C", "penalized_per_1k") for m in MODELS])
sub_A = np.mean([pa(m, "A", "substitutes_per_1k") for m in MODELS]); sub_C = np.mean([pa(m, "C", "substitutes_per_1k") for m in MODELS])
R["M4"] = {"penalized_per_1k_A": pen_A, "penalized_per_1k_C": pen_C, "penalized_drop": 1 - pen_C / pen_A if pen_A else None,
           "substitutes_per_1k_A": sub_A, "substitutes_per_1k_C": sub_C, "substitute_ratio": sub_C / sub_A if sub_A else None}
R["M4"]["pass"] = bool(R["M4"]["penalized_drop"] is not None and R["M4"]["penalized_drop"] >= 0.9
                       and R["M4"]["substitute_ratio"] is not None and R["M4"]["substitute_ratio"] >= 2)
(HERE / "RESULT_marker.json").write_text(json.dumps(R, indent=1, default=float))
for m in MODELS:
    print(f"== {m}")
    for a in "ABC":
        x = R[m]["arms"][a]
        print(f"  {a}: ans_ok {x['answerable_correct']}/24 (abst {x['answerable_abstained']})  una: abst {x['unanswerable_abstained']} wrong {x['unanswerable_wrong']} fail {x['unanswerable_fail']}  no_stop {x['no_stop']}  "
              f"median think {x['median_think_chars']:.0f} (una {x['median_think_unanswerable']:.0f})  total {x['total_think_chars']}  pen/1k {x['penalized_per_1k']:.2f} sub/1k {x['substitutes_per_1k']:.2f}  tok {x['completion_tokens_total']}")
    for a in "BC":
        print(f"  {a} vs A: {R[m][a + '_vs_A']}")
for k in ("M1", "M2", "M3", "M4"):
    print(k, R[k] if k != "M2" else {"pass": R["M2"]["pass"], **{m: R["M2"][m] for m in MODELS}})
