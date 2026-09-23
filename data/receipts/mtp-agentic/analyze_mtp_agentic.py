#!/usr/bin/env python3
"""Primary analysis for PREREG_MTP_AGENTIC.md.

usage: analyze_mtp_agentic.py RUNDIR   (RUNDIR holds OFF-s{1,2,3}.jsonl and MTP-s{1,2,3}.jsonl)

Rules, as pre-registered:
- pass = CORRECT, or CLARIFIED for expect.kind == no_action_ask (same table as argus_reps_compare)
- an INFRA row whose `why` mentions TimeoutError is a FAILURE, not a void
- judge void rule (INFRA, TOOL-FAIL) primary; noisefloor rule (+SUSPECT, NO-ATTEMPT) secondary
- unit = item: d_i = passrate(MTP) - passrate(OFF) over the seeds where BOTH arms are non-void
- mean d, 95 % t CI, 90 % t CI for TOST at +/-10 pp, exact sign-flip permutation p over items
"""
import itertools, json, math, random, sys
from collections import Counter, defaultdict
from pathlib import Path

RUN = Path(sys.argv[1])
A = Path(__file__).resolve().parents[3] / "argus"
PASS = {"actions": {"CORRECT"}, "no_action": {"CORRECT"}, "no_action_ask": {"CLARIFIED"}}
VOIDS = {"judge": {"INFRA", "TOOL-FAIL"}, "noisefloor": {"INFRA", "TOOL-FAIL", "SUSPECT", "NO-ATTEMPT"},
         # sensitivity only: timeouts treated as voids. A timeout is not always the model's fault
         # (harness, server, sandbox), so the primary rule counts it and this shows whether it matters.
         "judge_timeouts_void": {"INFRA", "TOOL-FAIL", "TIMEOUT-FAIL"}}
SEEDS = (1, 2, 3)
MARGIN = 0.10

d = json.load(open(A / "families_v4.json"))
items = d if isinstance(d, list) else d.get("items", d.get("scenarios"))
KIND = {i["id"]: i["expect"]["kind"] if isinstance(i["expect"], dict) else i["expect"] for i in items}


def load(label):
    rows = {}
    for ln in open(RUN / f"{label}.jsonl"):
        r = json.loads(ln)
        v = r["verdict"]
        if v == "INFRA" and "TimeoutError" in (r.get("why") or ""):
            v = "TIMEOUT-FAIL"
        rows[r["id"]] = {**r, "v": v}
    return rows


def t_quantile(p, df):  # inverse Student t via bisection on the regularized incomplete beta
    def cdf(t):
        x = df / (df + t * t)
        ib = betainc(df / 2, 0.5, x)
        return 1 - 0.5 * ib if t > 0 else 0.5 * ib
    lo, hi = -50.0, 50.0
    for _ in range(200):
        mid = (lo + hi) / 2
        (lo, hi) = (mid, hi) if cdf(mid) < p else (lo, mid)
    return (lo + hi) / 2


def betainc(a, b, x):  # continued fraction (Numerical Recipes)
    if x <= 0: return 0.0
    if x >= 1: return 1.0
    lbeta = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log(1 - x)
    if x > (a + 1) / (a + b + 2):
        return 1 - betainc(b, a, 1 - x)
    f, c, dd = 1.0, 1.0, 0.0
    for m in range(300):
        for step in (0, 1):
            if m == 0 and step == 0:
                num = 1.0
            elif step == 0:
                num = m * (b - m) * x / ((a + 2 * m - 1) * (a + 2 * m))
            else:
                num = -(a + m) * (a + b + m) * x / ((a + 2 * m) * (a + 2 * m + 1))
            dd = 1 + num * dd; dd = 1 / (dd if abs(dd) > 1e-300 else 1e-300)
            c = 1 + num / c if abs(c) > 1e-300 else 1e-300
            f *= c * dd
            if abs(c * dd - 1) < 1e-12: break
    return math.exp(lbeta) * (f - 1) / a


def signflip_p(ds):
    nz = [x for x in ds if abs(x) > 1e-12]
    obs = abs(sum(ds) / len(ds))
    if len(nz) <= 22:
        cnt = sum(1 for s in itertools.product((1, -1), repeat=len(nz))
                  if abs(sum(a * b for a, b in zip(s, nz)) / len(ds)) >= obs - 1e-12)
        return cnt / 2 ** len(nz), "exact"
    rng = random.Random(0); n = 1_000_000
    cnt = sum(1 for _ in range(n) if abs(sum(x * rng.choice((1, -1)) for x in nz) / len(ds)) >= obs - 1e-12)
    return (cnt + 1) / (n + 1), "monte-carlo 1e6"


def analyse(rule):
    off = {s: load(f"OFF-s{s}") for s in SEEDS}
    mtp = {s: load(f"MTP-s{s}") for s in SEEDS}
    void = VOIDS[rule]
    ds, per_item, dropped = [], {}, 0
    for iid, kind in KIND.items():
        po, pm, n = 0, 0, 0
        for s in SEEDS:
            ro, rm = off[s].get(iid), mtp[s].get(iid)
            if ro is None or rm is None or ro["v"] in void or rm["v"] in void:
                dropped += 1; continue
            po += ro["v"] in PASS[kind]; pm += rm["v"] in PASS[kind]; n += 1
        if n:
            ds.append((pm - po) / n); per_item[iid] = (po, pm, n)
    k = len(ds); mean = sum(ds) / k
    sd = math.sqrt(sum((x - mean) ** 2 for x in ds) / (k - 1)) if k > 1 else float("nan")
    se = sd / math.sqrt(k)
    t95, t90 = t_quantile(0.975, k - 1), t_quantile(0.95, k - 1)
    p, how = signflip_p(ds)
    ci90 = (mean - t90 * se, mean + t90 * se)
    return {"rule": rule, "items": k, "dropped_item_seed_pairs": dropped, "mean_d": mean, "sd_d": sd,
            "ci95": (mean - t95 * se, mean + t95 * se), "ci90": ci90, "p_signflip": p, "p_method": how,
            "equivalent_10pp": -MARGIN < ci90[0] and ci90[1] < MARGIN,
            "items_mtp_better": sum(x > 0 for x in ds), "items_mtp_worse": sum(x < 0 for x in ds),
            "pass_rate_off": sum(v[0] for v in per_item.values()) / sum(v[2] for v in per_item.values()),
            "pass_rate_mtp": sum(v[1] for v in per_item.values()) / sum(v[2] for v in per_item.values())}


def describe():
    out = {}
    for arm in [f"{a}-s{s}" for s in SEEDS for a in ("OFF", "MTP")]:
        rows = load(arm).values()
        out[arm] = {"n": len(rows), "verdicts": dict(Counter(r["v"] for r in rows)),
                    "timeouts": sum(r["v"] == "TIMEOUT-FAIL" for r in rows),
                    "tool_call_leaks": sum(bool((r.get("consumption") or {}).get("tool_call_leak")) for r in rows),
                    "median_secs": sorted(r["secs"] for r in rows)[len(rows) // 2]}
    return out


def timeouts():
    """Every timeout kept as its own record for root-cause analysis; never merged into failures."""
    out = []
    for arm in [f"{a}-s{s}" for s in SEEDS for a in ("OFF", "MTP")]:
        for r in load(arm).values():
            if r["v"] == "TIMEOUT-FAIL":
                out.append({"arm": arm, "id": r["id"], "secs": r["secs"], "why": r.get("why"),
                            "backend_calls": r.get("backend_calls"), "n_tool_calls": len(r.get("tool_calls") or []),
                            "ctx_used_peak": (r.get("consumption") or {}).get("ctx_used_peak")})
    return out


if __name__ == "__main__":
    res = {"primary": analyse("judge"), "secondary": analyse("noisefloor"),
           "sensitivity_timeouts_void": analyse("judge_timeouts_void"),
           "arms": describe(), "timeouts": timeouts()}
    print(json.dumps(res, indent=1, default=lambda x: list(x) if isinstance(x, tuple) else str(x)))
    (RUN / "ANALYSIS_mtp_agentic.json").write_text(json.dumps(res, indent=1, default=list))
