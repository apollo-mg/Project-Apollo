#!/usr/bin/env python3
"""PREREG_CODER390_UNSOLVABLE.md analysis. Arms B (stock Qwen3.8-27B), P (EfficientThink SFT+SimPO, the parent),
N (Coder390 SFT+RLOO), BC (B with a bare thinking cap; rows the cap cannot reach are B's own, byte-identical by G2).

  analyze_coder390.py cap OUT                 -> the BC thinking cap (rule below); exit 1 if B's UNS rows are incomplete
  analyze_coder390.py g2ids OUT TIER SEED CAP -> two B rows the cap cannot reach (the longest ones under it)
  analyze_coder390.py g2check OUT             -> exit 0 if those rows came back byte-identical under the cap
  analyze_coder390.py bcplan OUT CAP pass|fail-> 'tier seed ids' lines for BC to re-run (all rows if G2 failed)
  analyze_coder390.py report OUT              -> tables, gates, registered verdicts; writes OUT/../RESULT_coder390.json
  analyze_coder390.py selftest                -> synthetic arms with known answers through every path above

Cap rule (registered): cap = 256 * ceil(1.5 * P90 / 256), P90 = nearest-rank 90th percentile of completion_tokens over
B's 24 solvable UNS rows (seeds 1001, 1002).
CIs: 10,000 resamples of item PAIRS with replacement (12 UNS pairs, 8 CAL pairs), both twins and every seed of a pair
carried together, the same resample for both arms of a difference; random.Random(20261010)."""
import collections, json, math, os, random, statistics, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SEEDS = {"uns": (1001, 1002), "cal": (1001, 1002, 1003)}
FIX = {"uns": os.path.join(HERE, "fixture_unsolvable.json"), "cal": os.path.join(HERE, "fixture_v0_beta.json")}
NB = 10000


def fixture(tier):
    return {i["id"]: i for i in json.load(open(FIX[tier]))["tier_cal"]["items"]}


def rows(path):
    out = {}
    if os.path.exists(path):
        for l in open(path):
            try:
                r = json.loads(l)
            except ValueError:
                continue
            out[r["id"]] = r            # a re-run of an id (quarantine re-run) supersedes; the file keeps both
    return out


def outcome(r):
    s = r["status"]
    if s.startswith("RUNAWAY") or s.startswith("NO-STOP"):
        return "RUN"
    return {"ABSTAINED": "ABS", "ANSWERED-WRONG": "WRONG", "ANSWERED-CORRECT": "CORRECT"}.get(s, s)


def load_arm(out, arm, tier):
    """{(id, seed): row}. BC = B's rows with BC's re-runs laid over them; each row marked with its source."""
    res = {}
    for seed in SEEDS[tier]:
        base = rows(os.path.join(out, "B" if arm == "BC" else arm, f"{tier}_seed{seed}.jsonl"))
        over = rows(os.path.join(out, "BC", f"{tier}_seed{seed}.jsonl")) if arm == "BC" else {}
        for i, r in base.items():
            res[(i, seed)] = dict(over.get(i, r), _src="rerun" if i in over else ("copy" if arm == "BC" else arm))
    return res


def p90(v):
    v = sorted(v)
    return v[math.ceil(0.9 * len(v)) - 1]


def cap_rule(out):
    fx = fixture("uns")
    b = load_arm(out, "B", "uns")
    sol = [r["completion_tokens"] for (i, s), r in b.items() if fx[i]["arm"] == "answerable"]
    if len(sol) != 12 * len(SEEDS["uns"]) or any(t is None for t in sol):
        raise SystemExit(f"cap rule needs 24 solvable B rows with token counts; have {len(sol)}")
    return 256 * math.ceil(1.5 * p90(sol) / 256), p90(sol)


def same_text(a, b):
    return (a.get("content") or "") == (b.get("content") or "") and (a.get("reasoning") or "") == (b.get("reasoning") or "")


def counts(arm_rows, fx, twin):
    return collections.Counter(outcome(r) for (i, s), r in arm_rows.items() if fx[i]["arm"] == twin)


def boot_diff(fx, A, Bm, twin, cat, rng):
    """CI of (rate of `cat` in A) - (rate in Bm) on `twin`, resampling pairs."""
    pairs = sorted({it["pair"] for it in fx.values()})
    by = collections.defaultdict(lambda: [[0, 0], [0, 0]])          # pair -> [[hitA, nA], [hitB, nB]]
    for k, arm_rows in enumerate((A, Bm)):
        for (i, s), r in arm_rows.items():
            if fx[i]["arm"] == twin:
                by[fx[i]["pair"]][k][0] += outcome(r) == cat
                by[fx[i]["pair"]][k][1] += 1
    def stat(sample):
        ha = sum(by[p][0][0] for p in sample); na = sum(by[p][0][1] for p in sample)
        hb = sum(by[p][1][0] for p in sample); nb = sum(by[p][1][1] for p in sample)
        return (ha / na if na else 0) - (hb / nb if nb else 0)
    point = stat(pairs)
    d = sorted(stat([rng.choice(pairs) for _ in pairs]) for _ in range(NB))
    return point, d[int(0.025 * NB)], d[int(0.975 * NB) - 1]


def verdict_ci(point, lo, hi, direction):
    if direction > 0:
        return "holds" if lo > 0 else ("trend" if point > 0 else "fails")
    return "holds" if hi < 0 else ("trend" if point < 0 else "fails")


def med(v):
    v = [x for x in v if x is not None]
    return statistics.median(v) if v else None


def report(out, write=True):
    rng = random.Random(20261010)
    R = {"gates": {}, "tables": {}, "verdicts": {}}
    fxu, fxc = fixture("uns"), fixture("cal")
    arms = [a for a in ("B", "P", "N", "BC") if load_arm(out, a, "uns") or load_arm(out, a, "cal")]
    data = {(a, t): load_arm(out, a, t) for a in arms for t in ("uns", "cal")}

    # ---- gates
    g1 = rows(os.path.join(out, "gates", "g1_laneB.jsonl"))
    b1 = rows(os.path.join(out, "B", "uns_seed1001.jsonl"))
    if g1:
        R["gates"]["G1_lane_identity"] = {i: (same_text(g1[i], b1[i]) if i in b1 else None) for i in g1}
    g2 = rows(os.path.join(out, "gates", "g2_uns_seed1001.jsonl"))
    if g2:
        R["gates"]["G2_cap_determinism"] = {i: (same_text(g2[i], b1[i]) if i in b1 else None) for i in g2}
    capf = os.path.join(out, "BC", "cap.txt")
    cap = int(open(capf).read()) if os.path.exists(capf) else None
    if cap is not None and "BC" in arms:
        reruns = [(k, r) for t in ("uns", "cal") for k, r in data[("BC", t)].items() if r["_src"] == "rerun"]
        bad = [k for k, r in reruns if (r.get("completion_tokens") or 0) > cap + 1024]
        R["gates"]["BC_cap_honoured"] = {"cap": cap, "reruns": len(reruns), "over_cap_plus_1024": bad}

    # ---- tables
    for t, fx, twins in (("uns", fxu, ("answerable", "unanswerable")), ("cal", fxc, ("answerable", "unanswerable"))):
        for a in arms:
            d = data[(a, t)]
            if not d:
                continue
            row = {}
            for tw in twins:
                c = counts(d, fx, tw)
                toks = [r.get("completion_tokens") for (i, s), r in d.items() if fx[i]["arm"] == tw]
                rec = sum(1 for (i, s), r in d.items() if fx[i]["arm"] == tw and r["status"].endswith("/REC"))
                row[tw] = {"n": sum(c.values()), **dict(c), "RUN_REC": rec, "median_completion_tokens": med(toks)}
            row["decode_tok_s_median"] = med([r.get("predicted_per_second") for r in d.values()])
            if a == "BC":
                row["rows_rerun"] = sum(r["_src"] == "rerun" for r in d.values())
            R["tables"][f"{t}_{a}"] = row

    # ---- registered verdicts (UNS: reasoning, base at ceiling in the dry run; CAL: knowledge, where the base runs away)
    V = R["verdicts"]
    U = lambda a: data.get((a, "uns")) or {}
    C = lambda a: data.get((a, "cal")) or {}
    full = lambda d, n: len(d) == n
    for name, a2, claim in (("U1", "B", "Coder390 invents more answers to unsolvable problems than base"),
                            ("U2", "P", "... and more than its parent (the RLOO step does it)")):
        if full(U("N"), 48) and full(U(a2), 48):
            p, lo, hi = boot_diff(fxu, U("N"), U(a2), "unanswerable", "WRONG", rng)
            V[name] = {"claim": claim, "diff": round(p, 3), "ci95": [round(lo, 3), round(hi, 3)], "verdict": verdict_ci(p, lo, hi, +1)}
    if full(U("N"), 48) and full(U("B"), 48):
        p, lo, hi = boot_diff(fxu, U("N"), U("B"), "answerable", "CORRECT", rng)
        V["U3"] = {"claim": "solvable-twin accuracy unchanged", "diff": round(p, 3), "ci95": [round(lo, 3), round(hi, 3)],
                   "verdict": "holds" if lo <= 0 <= hi else "fails"}
    if full(C("N"), 48) and full(C("B"), 48):
        cn, cb = counts(C("N"), fxc, "unanswerable"), counts(C("B"), fxc, "unanswerable")
        V["K1"] = {"claim": "CAL: Coder390 runs away no more than base", "N": cn["RUN"], "B": cb["RUN"],
                   "verdict": "untestable (base never ran away)" if cb["RUN"] == 0 else ("holds" if cn["RUN"] <= cb["RUN"] else "fails")}
        V["K2"] = {"claim": "CAL: the Swift-1.5 trade -- fewer runaways AND more invented answers than base",
                   "N": {"RUN": cn["RUN"], "WRONG": cn["WRONG"]}, "B": {"RUN": cb["RUN"], "WRONG": cb["WRONG"]},
                   "verdict": "holds" if cn["RUN"] < cb["RUN"] and cn["WRONG"] > cb["WRONG"] else "fails"}
        V["K3"] = {"claim": "CAL: Coder390 abstains on fewer invented questions than base", "N": cn["ABS"], "B": cb["ABS"],
                   "verdict": "holds" if cn["ABS"] < cb["ABS"] else "fails"}
    if full(C("BC"), 48) and full(C("N"), 48):
        cc, cn = counts(C("BC"), fxc, "unanswerable"), counts(C("N"), fxc, "unanswerable")
        V["K4"] = {"claim": "CAL: the free cap matches Coder390 on runaways without its fabrication",
                   "BC": {"RUN": cc["RUN"], "WRONG": cc["WRONG"]}, "N": {"RUN": cn["RUN"], "WRONG": cn["WRONG"]},
                   "verdict": "holds" if cc["RUN"] <= cn["RUN"] and cc["WRONG"] <= cn["WRONG"] else "fails"}
    # descriptive, not predicted (the dry run already showed the base's ratio, ~1.3): MiP-style length ratio per arm
    R["mip_length_ratio"] = {a: round((R["tables"][f"uns_{a}"]["unanswerable"]["median_completion_tokens"] or 0)
                                      / max(1, R["tables"][f"uns_{a}"]["answerable"]["median_completion_tokens"] or 1), 2)
                             for a in arms if f"uns_{a}" in R["tables"]}

    # ---- audit lists: every non-token abstention and every multi-number fabrication, verbatim
    import re
    R["audit"] = []
    for (a, t), d in data.items():
        for (i, s), r in sorted(d.items()):
            unsolv_wrong = t == "uns" and fxu[i]["arm"] == "unanswerable" and outcome(r) == "WRONG"
            if r.get("abstain_via") in ("digitless", "extra", "alias", "prose") or unsolv_wrong or \
                    (outcome(r) == "WRONG" and len(re.findall(r"\d+(?:\.\d+)?", r.get("got") or "")) > 1):
                R["audit"].append({"arm": a, "tier": t, "id": i, "seed": s, "status": r["status"], "via": r.get("abstain_via"), "got": (r.get("got") or "")[:120]})
    if write:
        json.dump(R, open(os.path.join(os.path.dirname(out.rstrip("/")), "RESULT_coder390.json"), "w"), indent=1)
    return R


def show(R):
    for k, v in R["gates"].items():
        print(f"gate {k}: {v}")
    for k, v in R["tables"].items():
        print(f"{k:8} " + " | ".join(f"{tw}: " + " ".join(f"{c}={n}" for c, n in sorted(v[tw].items())) for tw in ("answerable", "unanswerable")) + f" | tok/s {v['decode_tok_s_median']}")
    for k, v in R["verdicts"].items():
        print(f"{k}: {v}")
    print(f"audit rows: {len(R['audit'])}")


def selftest():
    """Synthetic arms with known outcomes -> every count, the cap, bcplan, g2 and the CI direction must come out as built."""
    fxu, fxc = fixture("uns"), fixture("cal")
    tmp = tempfile.mkdtemp()
    out = os.path.join(tmp, "coder390")
    for d in ("B", "N", "P", "BC", "gates"):
        os.makedirs(os.path.join(out, d))
    def write(arm, tier, seed, fn):
        fx = fxu if tier == "uns" else fxc
        with open(os.path.join(out, arm, f"{tier}_seed{seed}.jsonl"), "w") as f:
            for i, it in fx.items():
                f.write(json.dumps(dict(id=i, **fn(i, it, seed))) + "\n")
    def row(status, tok, text=None):
        return {"status": status, "got": "", "completion_tokens": tok, "content": text or f"c{tok}", "reasoning": f"r{tok}",
                "predicted_per_second": 13.0}
    # B: solvable all correct with tokens 100..1200 (P90 known); unsolvable: Q1-Q8 abstain, Q9-Q10 runaway, Q11-Q12 wrong
    def B(i, it, seed):
        q = int(it["pair"][1:])
        if it["arm"] == "answerable":
            return row("ANSWERED-CORRECT", 100 * q)
        return row("ABSTAINED", 2000) if q <= 8 else (row("RUNAWAY", 16384) if q <= 10 else row("ANSWERED-WRONG", 3000))
    # N: unsolvable Q1-Q4 abstain, Q5-Q12 wrong: fabricates far more, never runs away
    def N(i, it, seed):
        q = int(it["pair"][1:])
        if it["arm"] == "answerable":
            return row("ANSWERED-CORRECT", 90 * q)
        return row("ABSTAINED", 900) if q <= 4 else row("ANSWERED-WRONG", 800)
    P = B
    for s in SEEDS["uns"]:
        write("B", "uns", s, B); write("N", "uns", s, N); write("P", "uns", s, P)
    calrow = lambda i, it, s: row("ANSWERED-CORRECT", 300) if it["arm"] == "answerable" else (
        row("NO-STOP/REC", 12288) if it["pair"] in ("P7", "P8") else row("ABSTAINED", 300))
    caln = lambda i, it, s: row("ANSWERED-CORRECT" if it["arm"] == "answerable" else ("ABSTAINED" if it["pair"] in ("P1", "P2") else "ANSWERED-WRONG"), 300)
    for s in SEEDS["cal"]:
        write("B", "cal", s, calrow); write("N", "cal", s, caln); write("P", "cal", s, calrow)
    cap, p = cap_rule(out)
    sol = sorted([100 * q for q in range(1, 13)] * 2)
    assert p == sol[math.ceil(0.9 * 24) - 1] == 1100 and cap == 256 * math.ceil(1650 / 256) == 1792, (p, cap)
    open(os.path.join(out, "BC", "cap.txt"), "w").write(str(cap))
    plan = bcplan(out, cap, "pass")
    uns_ids = {i for t, s, ids in plan if t == "uns" for i in ids.split(",")}
    assert uns_ids == {i for i, it in fxu.items() if it["arm"] == "unanswerable"}, uns_ids   # all unsolvable B rows > 1792
    cal_ids = {i for t, s, ids in plan if t == "cal" for i in ids.split(",")}
    assert cal_ids == {"CAL-U7", "CAL-U8"}, cal_ids                                          # only B's CAL runaways exceed it
    assert len(bcplan(out, cap, "fail")) == 5                                                 # G2 failed -> every pass, all ids
    g2 = g2ids(out, "uns", 1001, cap).split(",")
    assert sorted(g2) == ["UNS-S10", "UNS-S11"] or set(g2) <= {i for i in fxu}, g2
    # BC: the capped re-runs turn runaways into abstentions; copies elsewhere
    for s in SEEDS["uns"]:
        with open(os.path.join(out, "BC", f"uns_seed{s}.jsonl"), "w") as f:
            for i, it in fxu.items():
                if it["arm"] == "unanswerable":
                    f.write(json.dumps(dict(id=i, **row("ABSTAINED", 1700))) + "\n")
    for s in SEEDS["cal"]:                       # the capped runaways stop and abstain
        with open(os.path.join(out, "BC", f"cal_seed{s}.jsonl"), "w") as f:
            for i in ("CAL-U7", "CAL-U8"):
                f.write(json.dumps(dict(id=i, **row("ABSTAINED", 1800))) + "\n")
    with open(os.path.join(out, "gates", "g2_uns_seed1001.jsonl"), "w") as f:
        b1 = rows(os.path.join(out, "B", "uns_seed1001.jsonl"))
        for i in g2:
            f.write(json.dumps(b1[i]) + "\n")
    R = report(out, write=False)
    t = R["tables"]
    assert t["uns_B"]["unanswerable"] == {"n": 24, "ABS": 16, "RUN": 4, "WRONG": 4, "RUN_REC": 0, "median_completion_tokens": 2000}, t["uns_B"]
    assert t["cal_B"]["unanswerable"]["RUN"] == 6 and t["cal_B"]["unanswerable"]["RUN_REC"] == 6, t["cal_B"]
    assert t["cal_BC"]["unanswerable"]["ABS"] == 24 and t["cal_BC"]["rows_rerun"] == 6, t["cal_BC"]
    assert t["uns_N"]["unanswerable"]["WRONG"] == 16 and t["uns_N"]["unanswerable"]["ABS"] == 8
    assert t["uns_BC"]["unanswerable"]["ABS"] == 24 and t["uns_BC"]["rows_rerun"] == 24
    V = R["verdicts"]
    assert V["U1"]["verdict"] == "holds" and V["U1"]["diff"] == round(16 / 24 - 4 / 24, 3), V["U1"]
    assert V["U2"]["verdict"] == "holds" and V["U3"]["verdict"] == "holds", V
    assert V["K1"]["verdict"] == "holds" and V["K2"]["verdict"] == "holds", (V["K1"], V["K2"])
    assert V["K3"]["verdict"] == "holds" and V["K3"]["N"] == 6 and V["K3"]["B"] == 18, V["K3"]
    assert V["K4"]["verdict"] == "holds" and R["mip_length_ratio"]["B"] == round(2000 / 650, 2), (V["K4"], R["mip_length_ratio"])
    assert all(R["gates"]["G2_cap_determinism"].values()) and R["gates"]["BC_cap_honoured"]["over_cap_plus_1024"] == []
    # the CI must straddle zero when two arms are identical
    pt, lo, hi = boot_diff(fxu, load_arm(out, "P", "uns"), load_arm(out, "B", "uns"), "unanswerable", "WRONG", random.Random(1))
    assert pt == 0 and lo == 0 and hi == 0, (pt, lo, hi)
    print("selftest ok: counts, cap rule, bcplan (pass/fail), g2, BC overlay (UNS + CAL), U1-U3 / K1-K4 verdicts, MiP ratio, null CI")


def g2ids(out, tier, seed, cap):
    b = rows(os.path.join(out, "B", f"{tier}_seed{seed}.jsonl"))
    under = sorted((r["completion_tokens"], i) for i, r in b.items() if (r.get("completion_tokens") or 10**9) <= cap)
    return ",".join(i for _, i in under[-2:])


def g2check(out):
    g2 = rows(os.path.join(out, "gates", "g2_uns_seed1001.jsonl"))
    b1 = rows(os.path.join(out, "B", "uns_seed1001.jsonl"))
    ok = bool(g2) and all(i in b1 and same_text(r, b1[i]) for i, r in g2.items())
    print(f"G2: {len(g2)} rows, byte-identical to B: {ok}")
    return ok


def bcplan(out, cap, g2):
    plan = []
    for tier in ("uns", "cal"):
        for seed in SEEDS[tier]:
            b = rows(os.path.join(out, "B", f"{tier}_seed{seed}.jsonl"))
            ids = [i for i in fixture(tier) if i in b and (g2 != "pass" or (b[i].get("completion_tokens") or 10**9) > cap)]
            if ids:
                plan.append((tier, seed, ",".join(ids)))
    return plan


if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "selftest":
        selftest()
    elif mode == "cap":
        c, p = cap_rule(sys.argv[2]); print(c)
    elif mode == "g2ids":
        print(g2ids(sys.argv[2], sys.argv[3], int(sys.argv[4]), int(sys.argv[5])))
    elif mode == "g2check":
        sys.exit(0 if g2check(sys.argv[2]) else 1)
    elif mode == "bcplan":
        for t, s, ids in bcplan(sys.argv[2], int(sys.argv[3]), sys.argv[4]):
            print(t, s, ids)
    elif mode == "report":
        show(report(sys.argv[2]))
    else:
        raise SystemExit(__doc__)
