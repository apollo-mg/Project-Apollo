#!/usr/bin/env python3
"""Primary analysis for PREREG_MTP_AGENTIC_SPEED.md.  usage: analyze_mtp_speed.py RUNDIR"""
import json, math, random, sys
from pathlib import Path

RUN = Path(sys.argv[1]); SEEDS = (1, 2, 3); LIMIT = 2400.0
A = Path(__file__).resolve().parents[3] / "argus"
d = json.load(open(A / "families_v4.json")); items = d if isinstance(d, list) else d.get("items", d.get("scenarios"))
KIND = {i["id"]: i["expect"]["kind"] for i in items}
PASS = {"actions": {"CORRECT"}, "no_action": {"CORRECT"}, "no_action_ask": {"CLARIFIED"}}


def load(label):
    out = {}
    for ln in open(RUN / f"{label}.jsonl"):
        r = json.loads(ln)
        to = r["verdict"] == "INFRA" and "TimeoutError" in (r.get("why") or "")
        out[r["id"]] = {"secs": LIMIT if to else float(r["secs"]), "timeout": to,
                        "pass": r["verdict"] in PASS[KIND[r["id"]]], "v": r["verdict"],
                        "path": ([t["title"] for t in r["tool_calls"]], r.get("reply"))}
    return out


def tq(p, df):  # Student t quantile via normal approx + Cornish-Fisher (df >= 10 here)
    z = 1.959963985 if p == 0.975 else 1.644853627
    return z + (z**3 + z) / (4 * df) + (5 * z**5 + 16 * z**3 + 3 * z) / (96 * df**2)


off = {s: load(f"OFF-s{s}") for s in SEEDS}; mtp = {s: load(f"MTP-s{s}") for s in SEEDS}
per_item = []
for iid in KIND:
    lr = [math.log(mtp[s][iid]["secs"] / off[s][iid]["secs"]) for s in SEEDS if iid in off[s] and iid in mtp[s]]
    if lr: per_item.append(sum(lr) / len(lr))
k = len(per_item); m = sum(per_item) / k
sd = math.sqrt(sum((x - m) ** 2 for x in per_item) / (k - 1)); se = sd / math.sqrt(k); t = tq(0.975, k - 1)
rng = random.Random(0); obs = abs(m); N = 1_000_000
hits = sum(1 for _ in range(N) if abs(sum(x if rng.random() < .5 else -x for x in per_item) / k) >= obs - 1e-12)
prim = {"items": k, "geo_mean_ratio": math.exp(m), "ci95": [math.exp(m - t * se), math.exp(m + t * se)],
        "p_signflip_mc": (hits + 1) / (N + 1), "items_mtp_faster": sum(x < 0 for x in per_item)}


def arm_totals(arms):
    secs = sum(r["secs"] for a in arms.values() for r in a.values())
    passes = sum(r["pass"] for a in arms.values() for r in a.values())
    return secs, passes


so, po = arm_totals(off); sm, pm = arm_totals(mtp)
boot = []
ids = list(KIND)
for _ in range(20000):
    smp = [rng.choice(ids) for _ in ids]
    a = sum(off[s][i]["secs"] for i in smp for s in SEEDS); b = sum(off[s][i]["pass"] for i in smp for s in SEEDS)
    c = sum(mtp[s][i]["secs"] for i in smp for s in SEEDS); e = sum(mtp[s][i]["pass"] for i in smp for s in SEEDS)
    if b and e: boot.append((c / e) / (a / b))
boot.sort()
ett = {"off_secs_per_success": so / po, "mtp_secs_per_success": sm / pm, "ratio": (sm / pm) / (so / po),
       "ratio_ci95_boot": [boot[int(.025 * len(boot))], boot[int(.975 * len(boot))]],
       "pass_off": po / (len(KIND) * 3), "pass_mtp": pm / (len(KIND) * 3)}
split = {"identical": 0, "path_only": 0, "worse": 0, "better": 0, "label_only": 0}
for s in SEEDS:
    for i in KIND:
        a, b = off[s][i], mtp[s][i]
        if a["v"] == b["v"]: split["identical" if a["path"] == b["path"] else "path_only"] += 1
        elif a["pass"] == b["pass"]: split["label_only"] += 1
        else: split["worse" if a["pass"] else "better"] += 1
res = {"primary_time_ratio": prim, "expected_time_to_success": ett, "consequence_split": split,
       "timeouts": [(f"{arm}-s{s}", i) for arm, D in (("OFF", off), ("MTP", mtp)) for s in SEEDS
                    for i, r in D[s].items() if r["timeout"]]}
print(json.dumps(res, indent=1)); (RUN / "ANALYSIS_mtp_speed.json").write_text(json.dumps(res, indent=1))
