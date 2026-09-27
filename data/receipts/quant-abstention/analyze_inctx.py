#!/usr/bin/env python3
"""Score the in-context slot readout against PREREG_INCTX.md. Committed before any in-context output was opened.

Inputs: raw/inctx_<reader>__<writer>.jsonl (run_inctx.py), raw/main_*.jsonl and RESULT_main.json (forced slot and
generation, from main), arms_main.json. Writes RESULT_inctx.json.

Registered choices implemented here:
- Gate: Q8_0's own-prose probe pass rate must be >= 0.99 (else stop). Per arm, items failing the probe (in the arm's
  or Q8_0's own pass) are excluded and counted; an arm under 0.95 is flagged.
- Metrics, own prose, paired over valid items: timidity_ctx (H), confabulation_ctx (U), discrimination_ctx
  (within-template AUROC, U vs E+H). Main's statistics and levels: 1 - 0.05/60 for PTQ arms, 95 % for Bonsai.
  Labels by main's direction().
- H-ctx-rank: supported if >= 18 of 20 PTQ arms have |d disc| <= 0.03 with an interval including 0; not <= 14.
- H-ctx-confident: per confident-labelled file, (P_C - P_arm) forced minus (P_C - P_arm) in context on U items,
  95 % t-interval; "shrinks" if the lower bound > 0. Supported if >= 4 of 5; not if <= 1.
- Reading vs writing (7 key files, U items, confabulation direction, 95 %):
  total = C(C) - arm(arm); reading on Q8_0's prose = C(C) - arm(C); writing = C(C) - C(arm);
  reading on the arm's prose = C(arm) - arm(arm).
"""
import json
from pathlib import Path
import numpy as np
from analyze_main import load, t_interval, DiscBoot, direction, LEVEL

HERE = Path(__file__).resolve().parent
CONF5 = ["AD2XS", "AP3XXS", "APEXN", "EXL30", "EXL35"]
KEY7 = CONF5 + ["AD3XXS", "BON1"]


def rows(reader, writer):
    p = HERE / "raw" / f"inctx_{reader}__{writer}.jsonl"
    return load(p)[1] if p.exists() else None


def probe_rate(R):
    v = [r["probe"] for r in R.values()]
    return sum(v) / len(v) if v else float("nan")


def main():
    items = {x["id"]: x for x in map(json.loads, open(HERE / "corpus" / "M1.jsonl"))}
    reg = {x["arm"]: x for x in json.load(open(HERE / "arms_main.json"))["arms"]}
    main_res = json.load(open(HERE / "RESULT_main.json"))
    mainC = load(HERE / "raw" / "main_C.A.jsonl")[1]
    cC = rows("C", "C")
    out = {"gate": {"C_probe": probe_rate(cC), "C_n": len(cC)}, "arms": {}, "missing": []}
    if out["gate"]["C_probe"] < 0.99:
        out["gate"]["stop"] = True
        json.dump(out, open(HERE / "RESULT_inctx.json", "w"), indent=1, default=float)
        print("INSTRUMENT STOP: Q8_0 own-prose probe", out["gate"]["C_probe"]); return
    okC = {i for i, r in cC.items() if r["probe"]}
    for arm in reg:
        if arm == "C":
            continue
        A = rows(arm, arm)
        if A is None:
            out["missing"].append(arm); continue
        ptq = reg[arm]["category"] == "PTQ"
        level = LEVEL if ptq else 0.95
        ok = [i for i, r in A.items() if r["probe"] and i in okC]
        H = [i for i in ok if items[i]["arm"] == "H"]
        U = [i for i in ok if items[i]["arm"] == "U"]
        tim_m, tim_iv = t_interval([A[i]["P_abs"] - cC[i]["P_abs"] for i in H], level)
        con_m, con_iv = t_interval([cC[i]["P_abs"] - A[i]["P_abs"] for i in U], level)
        boot = DiscBoot({i: items[i] for i in ok})
        dc, drC = boot.point_and_draws({i: cC[i]["P_abs"] for i in ok})
        da, drA = boot.point_and_draws({i: A[i]["P_abs"] for i in ok})
        q = (1 - level) / 2
        dd = drA - drC
        disc_iv = (float(np.quantile(dd, q)), float(np.quantile(dd, 1 - q)))
        del boot, drC, drA, dd
        mt = main_res["tests"][arm]
        res = {"family": reg[arm]["family"], "category": reg[arm]["category"], "scored_bpw": reg[arm]["scored_bpw"],
               "probe": probe_rate(A), "flagged": probe_rate(A) < 0.95, "n_valid": len(ok),
               "n_excluded_probe": sum(1 for r in A.values() if not r["probe"]) + sum(1 for i in A if i not in okC and A[i]["probe"]),
               "timidity": {"diff": tim_m, "iv": tim_iv}, "confab": {"diff": con_m, "iv": con_iv},
               "discrimination": {"arm": da, "ceiling": dc, "diff": da - dc, "iv": disc_iv}, "level": level,
               "label_ctx": direction(tim_iv, con_iv, disc_iv), "label_main": mt["label"],
               "forced": {"tim": mt["timidity"]["diff"], "con": mt["confab"]["diff"], "disc": mt["discrimination"]["diff"]},
               "gen": {"tim": mt["gen_timidity"]["diff"], "con": mt["gen_confab"]["diff"]}}
        res["rank_preserved"] = abs(da - dc) <= 0.03 and disc_iv[0] <= 0 <= disc_iv[1]
        mA = load(HERE / "raw" / f"main_{arm}.jsonl")[1]
        if arm in CONF5:
            d = [(mainC[i]["P_abs"] - mA[i]["P_abs"]) - (cC[i]["P_abs"] - A[i]["P_abs"]) for i in U]
            m, iv = t_interval(d, 0.95)
            res["forced_minus_ctx_con"] = {"diff": m, "iv": iv, "n": len(d), "shrinks": iv[0] > 0}
        if arm in KEY7:
            aC, Ca = rows(arm, "C"), rows("C", arm)
            if aC is not None and Ca is not None:
                ids = [i for i in U if i in aC and i in Ca]
                comp = {"total": [cC[i]["P_abs"] - A[i]["P_abs"] for i in ids],
                        "reading_on_C_prose": [cC[i]["P_abs"] - aC[i]["P_abs"] for i in ids],
                        "writing": [cC[i]["P_abs"] - Ca[i]["P_abs"] for i in ids],
                        "reading_on_arm_prose": [Ca[i]["P_abs"] - A[i]["P_abs"] for i in ids]}
                res["decomposition"] = {"n": len(ids), **{k: dict(zip(("diff", "iv"), t_interval(v, 0.95)))
                                                          for k, v in comp.items()}}
        out["arms"][arm] = res
    ptq = [a for a, r in out["arms"].items() if r["category"] == "PTQ"]
    n_rank = sum(out["arms"][a]["rank_preserved"] for a in ptq)
    out["H_ctx_rank"] = {"n": n_rank, "of": len(ptq),
                         "verdict": "supported" if n_rank >= 18 else "not supported" if n_rank <= 14 else "partial"}
    shr = [a for a in CONF5 if out["arms"].get(a, {}).get("forced_minus_ctx_con", {}).get("shrinks")]
    out["H_ctx_confident"] = {"shrink": shr, "n": len(shr), "of": 5,
                              "verdict": "supported" if len(shr) >= 4 else "not supported" if len(shr) <= 1 else "partial"}
    json.dump(out, open(HERE / "RESULT_inctx.json", "w"), indent=1, default=float)
    print(f"gate: Q8_0 probe {out['gate']['C_probe']:.3f} (n {out['gate']['C_n']})  missing {out['missing']}")
    for a, r in out["arms"].items():
        print(f"{a:8s} probe {r['probe']:.3f} n {r['n_valid']:3d} | forced tim/con {r['forced']['tim']:+.3f}/{r['forced']['con']:+.3f}"
              f" | ctx tim {r['timidity']['diff']:+.3f} con {r['confab']['diff']:+.3f} [{r['confab']['iv'][0]:+.3f},{r['confab']['iv'][1]:+.3f}]"
              f" disc {r['discrimination']['diff']:+.3f} | gen {r['gen']['tim']:+.3f}/{r['gen']['con']:+.3f} | {r['label_main']} -> {r['label_ctx']}"
              + (f" | forced-ctx {r['forced_minus_ctx_con']['diff']:+.3f} [{r['forced_minus_ctx_con']['iv'][0]:+.3f},{r['forced_minus_ctx_con']['iv'][1]:+.3f}]" if "forced_minus_ctx_con" in r else ""))
        if "decomposition" in r:
            print("          " + "  ".join(f"{k} {v['diff']:+.3f} [{v['iv'][0]:+.3f},{v['iv'][1]:+.3f}]"
                                         for k, v in r["decomposition"].items() if k != "n"))
    print("H-ctx-rank:", out["H_ctx_rank"], "| H-ctx-confident:", out["H_ctx_confident"])


if __name__ == "__main__":
    main()
