#!/usr/bin/env python3
"""Score the main campaign against PREREG_MAIN.md. Written and committed before the first main arm runs.

Inputs: raw/main_<arm>.jsonl (header row + one row per M1 item), arms_main.json. The ceiling runs on both lanes
(raw/main_C.A.jsonl, raw/main_C.B.jsonl) for the bridge check; every arm is paired with the ceiling of its own lane.
Writes RESULT_main.json. `--pilot-smoke` runs the same code on the pilot's rows (C, M, L, B mapped to C, AD3XXS,
AD2XS, BON2) to test the statistics before any main data exists; its output is never a result.

Registered choices implemented here (PREREG_MAIN.md):
- Graded items only for R-gen rates; TRUNCATED / NO-ANSWER / INVALID excluded and counted.
- Primary metrics, paired against the ceiling:
  - timidity = mean P_abs on H;
  - confabulation = mean (1 - P_abs) on U;
  - discrimination = the within-template AUROC (U vs E+H), averaged over the 4 templates.
- Family: 20 PTQ arms x 3 metrics = 60. Level 1 - 0.05/60, two-sided.
  - Paired t-interval for timidity and confabulation.
  - 200,000-resample paired bootstrap for discrimination, stratified by template x item arm.
- Bonsai: 95 % intervals, outside the family.
- Validity gate: kappa >= 0.5. Below it, the direction label uses R-gen.
- Labels:
  - timid: timidity up, confabulation down;
  - confident: confabulation up, timidity flat;
  - shifted-down: timidity down, confabulation up (never counted for H-method);
  - mixed: both up;
  - noisy: discrimination down, both flat;
  - none: anything else.
- H-method and H-knee exactly as registered.
"""
import argparse, json, math
from pathlib import Path
import numpy as np
from scipy import stats

HERE = Path(__file__).resolve().parent
T = ("capital", "novel", "opera", "university")
GRADED = {"CORRECT", "WRONG", "ABSTAINED"}
N_FAMILY = 60
LEVEL = 1 - 0.05 / N_FAMILY
B = 200_000
BINS = [(2.4, 2.9), (2.9, 3.3), (3.3, 3.7), (3.7, 4.2)]
CAPABLE = ["AD", "UD", "GSQ", "AP"]


def load(path):
    rows = [json.loads(l) for l in open(path)]
    return rows[0], {r["id"]: r for r in rows[1:]}


def t_interval(d, level):
    d = np.asarray(d, float)
    n, m = len(d), float(np.mean(d))
    if n < 2:
        return m, (float("nan"), float("nan"))
    h = stats.t.ppf(1 - (1 - level) / 2, n - 1) * float(np.std(d, ddof=1)) / math.sqrt(n)
    return m, (m - h, m + h)


def auroc_matrix(pos, neg):
    d = np.asarray(pos)[:, None] - np.asarray(neg)[None, :]
    return (d > 0).astype(float) + 0.5 * (d == 0)


class DiscBoot:
    """Stratified paired bootstrap of the within-template AUROC mean. Counts are drawn once (fixed seed) and reused
    for every arm, so all arms and the ceiling are resampled identically (paired)."""

    def __init__(self, items, n_boot=B, seed=20260927):
        rng = np.random.default_rng(seed)
        self.cells, self.w = {}, {}
        for t in T:
            for arm in "EHU":
                ids = [i for i, it in items.items() if it["template"] == t and it["arm"] == arm]
                if ids:
                    self.cells[(t, arm)] = ids
                    self.w[(t, arm)] = rng.multinomial(len(ids), [1 / len(ids)] * len(ids), size=n_boot).astype(np.float32)

    def point_and_draws(self, P):
        pt, draws = [], []
        for t in T:
            pos = self.cells[(t, "U")]
            negE, negH = self.cells.get((t, "E"), []), self.cells.get((t, "H"), [])
            M = auroc_matrix([P[i] for i in pos], [P[i] for i in negE + negH]).astype(np.float32)
            pt.append(float(M.mean()))
            wn = np.concatenate([self.w[(t, a)] for a in "EH" if (t, a) in self.w], axis=1)
            wp = self.w[(t, "U")]
            draws.append(np.einsum("bi,ij,bj->b", wp, M, wn) / (wp.sum(1) * wn.sum(1)))
        return float(np.mean(pt)), np.mean(draws, axis=0)


def kappa(rows):
    g = [r for r in rows if r["grade"] in GRADED]
    n = len(g)
    s = sum(r["P_abs"] > 0.5 for r in g); a = sum(r["grade"] == "ABSTAINED" for r in g)
    po = sum((r["P_abs"] > 0.5) == (r["grade"] == "ABSTAINED") for r in g) / n
    pe = (s * a + (n - s) * (n - a)) / n ** 2
    return (po - pe) / (1 - pe) if pe < 1 else float("nan")


def arm_summary(R, items):
    by = lambda arm: [R[i] for i in R if items[i]["arm"] == arm]
    g = lambda arm: [r for r in by(arm) if r["grade"] in GRADED]
    rate = lambda xs: sum(xs) / len(xs) if xs else float("nan")
    return {
        "timidity_H": rate([r["P_abs"] for r in by("H")]), "timidity_E": rate([r["P_abs"] for r in by("E")]),
        "confab_U": rate([1 - r["P_abs"] for r in by("U")]),
        "knowledge_E": rate([r["grade"] == "CORRECT" for r in g("E")]),
        "knowledge_H": rate([r["grade"] == "CORRECT" for r in g("H")]),
        "knowledge_H_lenient": rate([r["grade_lenient"] == "CORRECT" for r in g("H")]),
        "U_wrong_gen": rate([r["grade"] == "WRONG" for r in g("U")]),
        "H_overabstain_gen": rate([r["grade"] == "ABSTAINED" for r in g("H")]),
        "kappa": kappa(list(R.values())),
        "never_abstain_baseline": rate([r["grade"] != "ABSTAINED" for r in R.values() if r["grade"] in GRADED]),
        "not_graded": {k: sum(r["grade"] == k for r in R.values()) for k in ("TRUNCATED", "NO-ANSWER", "INVALID")},
        "truncated_frac": sum(r["grade"] == "TRUNCATED" for r in R.values()) / len(R),
        "per_template": {t: {"timidity_H": rate([r["P_abs"] for r in by("H") if items[r["id"]]["template"] == t]),
                             "confab_U": rate([1 - r["P_abs"] for r in by("U") if items[r["id"]]["template"] == t]),
                             "U_abstain_gen": rate([r["grade"] == "ABSTAINED" for r in g("U") if items[r["id"]]["template"] == t]),
                             "H_correct_gen": rate([r["grade"] == "CORRECT" for r in g("H") if items[r["id"]]["template"] == t])}
                         for t in T},
    }


def direction(tim, con, disc):
    """each argument: (lo, hi) interval of arm - ceiling"""
    up = lambda iv: iv[0] > 0
    down = lambda iv: iv[1] < 0
    flat = lambda iv: iv[0] <= 0 <= iv[1]
    if up(tim) and down(con):
        return "timid"
    if up(con) and flat(tim):
        return "confident"
    if down(tim) and up(con):
        return "shifted-down"
    if up(tim) and up(con):
        return "mixed"
    if down(disc) and flat(tim) and flat(con):
        return "noisy"
    return "none"


def compare(RC, RA, items, boot, level):
    ids = [i for i in RC if i in RA]
    H = [i for i in ids if items[i]["arm"] == "H"]
    U = [i for i in ids if items[i]["arm"] == "U"]
    tim_m, tim_iv = t_interval([RA[i]["P_abs"] - RC[i]["P_abs"] for i in H], level)
    con_m, con_iv = t_interval([RC[i]["P_abs"] - RA[i]["P_abs"] for i in U], level)   # (1-pa) - (1-pc)
    dc, drawsC = boot.point_and_draws({i: RC[i]["P_abs"] for i in ids})
    da, drawsA = boot.point_and_draws({i: RA[i]["P_abs"] for i in ids})
    dd = drawsA - drawsC
    q = (1 - level) / 2
    disc_iv = (float(np.quantile(dd, q)), float(np.quantile(dd, 1 - q)))
    out = {"timidity": {"diff": tim_m, "iv": tim_iv}, "confab": {"diff": con_m, "iv": con_iv},
           "discrimination": {"arm": da, "ceiling": dc, "diff": da - dc, "iv": disc_iv}}
    # R-gen fallback for the validity gate
    gH = [i for i in H if RA[i]["grade"] in GRADED and RC[i]["grade"] in GRADED]
    gU = [i for i in U if RA[i]["grade"] in GRADED and RC[i]["grade"] in GRADED]
    out["gen_timidity"] = dict(zip(("diff", "iv"), t_interval(
        [(RA[i]["grade"] == "ABSTAINED") - (RC[i]["grade"] == "ABSTAINED") for i in gH], level)))
    out["gen_confab"] = dict(zip(("diff", "iv"), t_interval(
        [(RA[i]["grade"] == "WRONG") - (RC[i]["grade"] == "WRONG") for i in gU], level)))
    return out


def bridge(pa, pb):
    ha, A = load(pa); hb, Bv = load(pb)
    bad_slot, bad_text, worst = [], [], 0.0
    for i in A:
        if i not in Bv:
            bad_slot.append(i); continue
        sa, sb = A[i]["slot_top"], Bv[i]["slot_top"]
        if [x[0] for x in sa] != [x[0] for x in sb]:
            bad_slot.append(i)
        else:
            dmax = max(abs(x[2] - y[2]) for x, y in zip(sa, sb))
            worst = max(worst, dmax)
            if dmax > 1e-6:
                bad_slot.append(i)
        if A[i]["content"] != Bv[i]["content"]:
            bad_text.append(i)
    return {"items": len(A), "slot_mismatch": len(bad_slot), "text_mismatch": len(bad_text),
            "max_logprob_diff": worst, "pass": not bad_slot and not bad_text,
            "examples": (bad_slot + bad_text)[:5]}


def knee(family_rungs):
    """family_rungs: [(bpw, distinguishable_bool)] -> (knee_bpw | None, status)"""
    r = sorted(family_rungs)
    dist = [d for _, d in r]
    monotone = all(not (dist[j] and not dist[k]) for k in range(len(r)) for j in range(k + 1, len(r)))
    if not any(dist):
        return None, "no knee in range (did not degrade)", monotone
    if all(dist):
        return None, "all rungs distinguishable (knee above range)", monotone
    for k, (bpw, d) in enumerate(r):
        if not d:
            if k == 0:
                return None, "lowest rung indistinguishable", monotone
            if all(dist[:k]):
                return bpw, "knee", monotone
            break
    return None, "non-monotone", monotone


def bin_of(bpw):
    return next((j for j, (lo, hi) in enumerate(BINS) if lo <= bpw < hi), None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pilot-smoke", action="store_true")
    a = ap.parse_args()
    reg = {x["arm"]: x for x in json.load(open(HERE / "arms_main.json"))["arms"]}
    if a.pilot_smoke:
        items = {x["id"]: x for x in map(json.loads, open(HERE / "corpus" / "P0.jsonl"))}
        m = {"C": "C", "AD3XXS": "M", "AD2XS": "L", "BON2": "B"}
        runs = {arm: {"rows": load(HERE / "raw" / f"pilot_{p}.jsonl")[1], "lane": "A"} for arm, p in m.items()}
        ceil = {"A": runs["C"]["rows"]}
        bridge_res = {"skipped": "pilot smoke"}
    else:
        items = {x["id"]: x for x in map(json.loads, open(HERE / "corpus" / "M1.jsonl"))}
        runs, ceil = {}, {}
        for lane in "AB":
            p = HERE / "raw" / f"main_C.{lane}.jsonl"
            if p.exists():
                ceil[lane] = load(p)[1]
        bridge_res = bridge(HERE / "raw" / "main_C.A.jsonl", HERE / "raw" / "main_C.B.jsonl") \
            if len(ceil) == 2 else {"skipped": "one lane"}
        for arm in reg:
            if arm == "C":
                continue
            p = HERE / "raw" / f"main_{arm}.jsonl"
            if p.exists():
                hdr, R = load(p)
                runs[arm] = {"rows": R, "lane": hdr.get("meta", {}).get("lane", "A")}
    boot = DiscBoot(items)
    out = {"bridge": bridge_res, "level_family": LEVEL, "arms": {}, "tests": {}}
    for arm, run in runs.items():
        out["arms"][arm] = {**{k: reg[arm][k] for k in ("family", "category", "label", "scored_bpw")},
                            "lane": run["lane"], **arm_summary(run["rows"], items)}
    for arm, run in runs.items():
        if arm == "C":
            continue
        fam = reg[arm]["family"]
        level = LEVEL if reg[arm]["category"] == "PTQ" else 0.95
        c = compare(ceil[run["lane"]], run["rows"], items, boot, level)
        valid = out["arms"][arm]["kappa"] >= 0.5
        if valid:
            lab = direction(c["timidity"]["iv"], c["confab"]["iv"], c["discrimination"]["iv"])
        else:
            lab = direction(c["gen_timidity"]["iv"], c["gen_confab"]["iv"], c["discrimination"]["iv"])
        out["tests"][arm] = {**c, "level": level, "valid_r_slot": valid, "label": lab,
                             "label_source": "R-slot" if valid else "R-gen (kappa < 0.5)",
                             "in_family": reg[arm]["category"] == "PTQ", "family": fam, "scored_bpw": reg[arm]["scored_bpw"]}
    # H-method
    hm = []
    for j, (lo, hi) in enumerate(BINS):
        inbin = [(arm, t) for arm, t in out["tests"].items() if t["in_family"] and t["scored_bpw"] and lo <= t["scored_bpw"] < hi]
        for x, tx in inbin:
            for y, ty in inbin:
                if tx["family"] != ty["family"] and tx["label"] == "timid" and ty["label"] == "confident":
                    hm.append({"bin": [lo, hi], "timid": x, "confident": y})
    out["H_method"] = {"supported": bool(hm), "pairs": hm}
    # H-knee
    fams = {}
    for arm, t in out["tests"].items():
        if t["in_family"] and t["scored_bpw"]:
            iv = t["discrimination"]["iv"]
            fams.setdefault(t["family"], []).append((t["scored_bpw"], not (iv[0] <= 0 <= iv[1])))
    kn = {f: dict(zip(("knee_bpw", "status", "monotone"), knee(r))) for f, r in fams.items()}
    with_knee = [f for f in CAPABLE if kn.get(f, {}).get("knee_bpw") is not None]
    bins_ = {bin_of(kn[f]["knee_bpw"]) for f in with_knee}
    out["H_knee"] = {"families": kn, "capable_with_knee": with_knee,
                     "supported": len(with_knee) >= 3 and len(bins_) == 1 and all(v["monotone"] for v in kn.values())}
    # descriptive: without operas
    items_no = {i: it for i, it in items.items() if it["template"] != "opera"}
    out["without_opera"] = {}
    for arm, run in runs.items():
        if arm == "C":
            continue
        C = {i: r for i, r in ceil[run["lane"]].items() if i in items_no}
        A = {i: r for i, r in run["rows"].items() if i in items_no}
        tm, tiv = t_interval([A[i]["P_abs"] - C[i]["P_abs"] for i in A if items[i]["arm"] == "H"], out["tests"][arm]["level"])
        cm, civ = t_interval([C[i]["P_abs"] - A[i]["P_abs"] for i in A if items[i]["arm"] == "U"], out["tests"][arm]["level"])
        out["without_opera"][arm] = {"timidity": {"diff": tm, "iv": tiv}, "confab": {"diff": cm, "iv": civ}}
    out["hard_correct_at_ceiling"] = {lane: arm_summary(ceil[lane], items)["knowledge_H"] for lane in ceil}
    name = "RESULT_main_SMOKE.json" if a.pilot_smoke else "RESULT_main.json"
    json.dump(out, open(HERE / name, "w"), indent=1, default=float)
    for arm, t in out["tests"].items():
        print(f"{arm:8s} {t['scored_bpw']!s:>6}  tim {t['timidity']['diff']:+.3f} [{t['timidity']['iv'][0]:+.3f},{t['timidity']['iv'][1]:+.3f}]"
              f"  con {t['confab']['diff']:+.3f} [{t['confab']['iv'][0]:+.3f},{t['confab']['iv'][1]:+.3f}]"
              f"  disc {t['discrimination']['diff']:+.3f} [{t['discrimination']['iv'][0]:+.3f},{t['discrimination']['iv'][1]:+.3f}]"
              f"  kappa {out['arms'][arm]['kappa']:.2f}  -> {t['label']}")
    print("H-method:", out["H_method"]["supported"], "| H-knee:", out["H_knee"]["supported"], out["H_knee"]["families"])
    print("bridge:", out["bridge"])


if __name__ == "__main__":
    main()
