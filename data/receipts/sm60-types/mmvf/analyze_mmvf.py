#!/usr/bin/env python3
"""PREREG_MMVF_SHORTROW.md analysis. Phase A applies the registered selection rule; phase B scores B1-B4.

  analyze_mmvf.py A RAW_A_DIR            -> selection (R*, KMAX*), mechanism table, correctness of tbo-base/tbo-tune
  analyze_mmvf.py B RAW_B_DIR RAW_A_DIR KMAX -> B1-B4 verdicts at the KMAX the final binary was built with
  analyze_mmvf.py --self-test            -> synthetic checks of the parser, the rule and the verdicts
"""
import json, re, statistics, sys, tempfile
from pathlib import Path

GRID_K = [64, 128, 256, 320, 384, 512, 768, 1024, 1536, 2048]
GRID_N = [1, 4]
RS = [1, 2, 4, 8]
HELD_OUT = [("bf16", 10240, 1, 320), ("f32", 10240, 1, 320), ("f16", 32000, 2, 192), ("f32", 16384, 1, 96),
            ("f16", 4096, 1, 448), ("bf16", 8192, 8, 640), ("bf16", 2048, 1, 256)]
CONTROLS = [("f16", 4096, 1, 4096), ("bf16", 320, 1, 10240), ("f16", 320, 1, 10240)]
PERF = re.compile(r"MUL_MAT\(type_a=(\w+),type_b=f32,m=(\d+),n=(\d+),k=(\d+),bs=\[1,1\],nr=\[1,1\][^)]*\):"
                  r"\s+(\d+) runs -\s+([\d.]+) us/run")
ANSI = re.compile(r"\x1b\[[0-9;]*m")
TEST = re.compile(r"^\s+((?:MUL_MAT|MUL_MAT_ID|MUL_MAT_VEC_FUSION)\(.*\)):\s+(OK|FAIL)\b", re.M)


def parse_perf(path):
    """{(type, m, n, k): mean us/run within this file} (duplicate shapes, if any, are averaged)."""
    acc = {}
    for t, m, n, k, _runs, us in PERF.findall(ANSI.sub("", Path(path).read_text(errors="replace"))):
        acc.setdefault((t, int(m), int(n), int(k)), []).append(float(us))
    return {key: sum(v) / len(v) for key, v in acc.items()}


def medians(raw, arm):
    """median over reps of each shape for one arm: files perf_<arm>_r<rep>.txt"""
    reps = [parse_perf(p) for p in sorted(Path(raw).glob(f"perf_{arm}_r[0-9].txt"))]
    keys = set().union(*reps) if reps else set()
    return {k: statistics.median([r[k] for r in reps if k in r]) for k in keys}, len(reps)


def parse_test(path):
    txt = ANSI.sub("", Path(path).read_text(errors="replace"))   # results are colour-coded: ESC[1;32mOK ESC[0m
    res = {}
    for case, st in TEST.findall(txt):
        res[case] = "FAIL" if res.get(case) == "FAIL" else st
    m = re.search(r"(\d+)/(\d+) tests passed", txt)
    return res, (m.group(0) if m else None)


def select(t):
    """t[arm][(type,m,n,k)] -> (R*, KMAX*|None, sums). The registered rule, nothing else."""
    def cell(arm, k, n):
        return t[arm][("f16", 10240, n, k)]
    sums = {r: sum(cell(f"R{r}", k, n) for k in GRID_K if k <= 512 for n in GRID_N) for r in RS}
    best = min(sums.values())
    rstar = min(r for r in RS if sums[r] <= best * 1.01)
    kmax = None
    for k in GRID_K:
        if all(cell(f"R{rstar}", kk, n) <= 0.97 * cell("base", kk, n) for kk in GRID_K if kk <= k for n in GRID_N):
            kmax = k
        else:
            break
    return rstar, kmax, sums


def select_revised(t, rstar, cap=1792):
    """Deviation 2 (post-hoc, after phase A): the registered rule demanded a >= 3 % gain in every cell from k=64, and
    k=64/n=4 sits at the ~20 us harness floor for every arm. Revised: KMAX = the largest grid k <= cap (the prereg's
    FP16 half2-chain note: k/64 <= 28) such that no cell k' <= k regresses (t(R*) <= 1.03 t(base), both n) and k
    itself gains (t(R*) <= 0.97 t(base), both n). R* stays the registered argmin."""
    def r(k, n):
        return t[f"R{rstar}"][("f16", 10240, n, k)] / t["base"][("f16", 10240, n, k)]
    kmax = None
    for k in GRID_K:
        if k > cap or any(r(k, n) > 1.03 for n in GRID_N):
            break
        if all(r(k, n) <= 0.97 for n in GRID_N):
            kmax = k
    return kmax


def phase_a(raw):
    t, nrep = {}, {}
    for arm in ["base", "unset"] + [f"R{r}" for r in RS]:
        t[arm], nrep[arm] = medians(raw, arm)
    rstar, kmax, sums = select(t)
    kmax_rev = select_revised(t, rstar)
    mech = []
    for n in GRID_N:
        for k in GRID_K:
            key = ("f16", 10240, n, k)
            row = {"n": n, "k": k, "base_us": t["base"][key], "unset_vs_base": t["unset"][key] / t["base"][key]}
            row.update({f"R{r}_vs_base": t[f"R{r}"][key] / t["base"][key] for r in RS})
            mech.append(row)
    tb, sb = parse_test(Path(raw) / "test_base.txt")
    tt, st = parse_test(Path(raw) / "test_tune_R4.txt")
    new_fail = sorted(c for c, s in tt.items() if s == "FAIL" and tb.get(c) == "OK")
    return {"reps": nrep, "R_star": rstar, "KMAX_star": kmax, "KMAX_dev2_posthoc": kmax_rev,
            "sum_k_le_512_us": sums, "grid": mech,
            "test_base": {"summary": sb, "cases": len(tb), "fail": sum(s == "FAIL" for s in tb.values())},
            "test_tune_R4": {"summary": st, "cases": len(tt), "fail": sum(s == "FAIL" for s in tt.values()),
                             "fail_where_base_ok": new_fail[:20], "n_fail_where_base_ok": len(new_fail),
                             "missing_vs_base": len(set(tb) - set(tt))}}


def phase_b(raw, kmax):
    base, nb = medians(raw, "base")
    fin, nf = medians(raw, "final")
    ratio = {k: fin[k] / base[k] for k in base if k in fin}
    hu = [ratio[s] for s in HELD_OUT[:2]]
    b2_shapes = [s for s in HELD_OUT if kmax is not None and s[3] <= kmax]
    confirm = HELD_OUT + CONTROLS + [("f16", 10240, n, k) for n in GRID_N for k in GRID_K]
    worst = max(confirm, key=lambda s: ratio[s])
    tb, _ = parse_test(Path(raw).parent / "raw_A" / "test_base.txt") if (Path(raw).parent / "raw_A").exists() \
        else parse_test(Path(raw) / "test_base.txt")
    tf, sf = parse_test(Path(raw) / "test_final.txt")
    new_fail = sorted(c for c in tb if tb[c] == "OK" and tf.get(c) != "OK")
    v = {
        "B1": {"holds": all(r <= 0.50 for r in hu), "hc_up_ratio_bf16_f32": hu},
        "B2": {"holds": bool(b2_shapes) and all(ratio[s] <= 0.80 for s in b2_shapes),
               "shapes": {str(s): ratio[s] for s in b2_shapes}},
        "B3": {"holds": all(ratio[s] <= 1.03 for s in confirm), "worst_shape": str(worst), "worst_ratio": ratio[worst]},
        "B4": {"holds": not new_fail, "final_summary": sf, "not_ok_where_base_ok": new_fail[:20],
               "n_not_ok_where_base_ok": len(new_fail)},
    }
    return {"reps": {"base": nb, "final": nf}, "verdicts": v,
            "ratios": {str(k): {"base_us": base[k], "final_us": fin[k], "ratio": r} for k, r in sorted(ratio.items())}}


def _write_perf(path, cells):
    lines = ["ggml_cuda_init: noise line on stdout is harmless"]
    for (t, m, n, k), us in cells.items():
        lines.append(f"  MUL_MAT(type_a={t},type_b=f32,m={m},n={n},k={k},bs=[1,1],nr=[1,1],per=[0,1,2,3],k_v=0,o=1,"
                     f"src_overlap=0):                   16380 runs - {us:8.2f} us/run -   6.55 MFLOP/run - 79 GFLOPS")
    Path(path).write_text("\n".join(lines) + "\n")


def self_test():
    fails = []
    def check(name, cond):
        print(("PASS  " if cond else "FAIL  ") + name)
        if not cond:
            fails.append(name)
    shapes = [("f16", 10240, n, k) for n in GRID_N for k in GRID_K] + HELD_OUT + CONTROLS
    def base_us(s):
        return 80.0 if s[3] <= 512 else 20.0 + s[3] / 50
    # scenario 1: R4 best; R4 beats base by >3 % up to k=1024 and fails at 1536 (n=4 only)
    def arm_us(arm, s):
        b = base_us(s)
        if arm in ("base", "unset"):
            return b
        r = int(arm[1:])
        f = {1: 0.60, 2: 0.45, 4: 0.40, 8: 0.405}[r]
        if s[3] >= 1536 and s[2] == 4:
            f = 0.99
        elif s[3] >= 1536:
            f = 0.90
        return b * f
    with tempfile.TemporaryDirectory() as d:
        A = Path(d) / "raw_A"; A.mkdir()
        for rep in (1, 2, 3):
            for arm in ["base", "unset", "R1", "R2", "R4", "R8"]:
                _write_perf(A / f"perf_{arm}_r{rep}.txt", {s: arm_us(arm, s) * (1 + 0.001 * rep) for s in shapes})
        ok = "  MUL_MAT(type_a=f16,type_b=f32,m=7,n=1,k=64): OK\n"
        (A / "test_base.txt").write_text(ok + "  MUL_MAT(type_a=f16,type_b=f32,m=7,n=2,k=64): OK\n2/2 tests passed\n")
        (A / "test_tune_R4.txt").write_text(ok + "  MUL_MAT(type_a=f16,type_b=f32,m=7,n=2,k=64): FAIL\n1/2 tests passed\n")
        a = phase_a(A)
        check("parser reads every shape x 3 reps", a["reps"]["R4"] == 3 and len(a["grid"]) == 20)
        check("R* = 4 (R8 within 1.25 % is not a tie)", a["R_star"] == 4)
        check("KMAX* = 1024 (k=1536 fails at n=4)", a["KMAX_star"] == 1024)
        check("a FAIL where base was OK is reported", a["test_tune_R4"]["n_fail_where_base_ok"] == 1)
        # tie rule: R2 within 1 % of R4 -> smaller R wins
        t = {arm: {s: arm_us(arm, s) for s in shapes} for arm in ["base", "R1", "R2", "R4", "R8"]}
        t["R2"] = {s: t["R4"][s] * 1.005 for s in shapes}
        check("tie within 1 % goes to the smaller R", select(t)[0] == 2)
        # real line format from .73 (10-01): colour-coded result, m_v/pad params
        (A / "ansi.txt").write_text("  MUL_MAT(type_a=f16,type_b=f32,m=7,n=1,k=64,bs=[1,1],nr=[1,1],per=[0,1,2,3],k_v=0,"
                                    "o=1,src_overlap=0,m_v=0,pad=0): \x1b[1;32mOK\x1b[0m\n"
                                    "  MUL_MAT_ID(type_a=bf16,type_b=f32,n_mats=16,n_used=4,b=0,m=1001,n=4,k=320,o=1): "
                                    "\x1b[1;31mFAIL\x1b[0m\n  1/2 tests passed\n")
        r, summ = parse_test(A / "ansi.txt")
        check("colour-coded OK/FAIL lines parse", sorted(r.values()) == ["FAIL", "OK"] and summ == "1/2 tests passed")
        # Deviation 2 selector: a floor cell (ratio ~1.0) at k=64 no longer blocks; the cap and regressions do
        t3 = {arm: {s: arm_us(arm, s) for s in shapes} for arm in ["base", "R1", "R2", "R4", "R8"]}
        for n in GRID_N:   # the floor hits every arm, as on .73
            for arm in ["R1", "R2", "R4", "R8"]:
                t3[arm][("f16", 10240, n, 64)] = t3["base"][("f16", 10240, n, 64)] * 1.005
        check("registered rule is null on a floor cell at k=64", select(t3)[1] is None)
        check("revised rule skips the floor cell and stops at the regression-free gain edge (1024)",
              select_revised(t3, 4) == 1024)
        check("revised rule respects the FP16 cap", select_revised(t3, 4, cap=512) == 512)
        t3["R4"][("f16", 10240, 4, 384)] = t3["base"][("f16", 10240, 4, 384)] * 1.05
        check("a >3 % regression ends the revised range below it", select_revised(t3, 4) == 320)
        # null: k=64 fails
        t2 = {arm: {s: base_us(s) for s in shapes} for arm in ["base", "R1", "R2", "R4", "R8"]}
        check("no gain at k=64 -> KMAX* is None", select(t2)[1] is None)
        # phase B: final = R4 rule with KMAX 1024
        B = Path(d) / "raw_B"; B.mkdir()
        def fin_us(s):
            return arm_us("R4", s) if s[3] <= 1024 else base_us(s)
        for rep in (1, 2, 3):
            _write_perf(B / f"perf_base_r{rep}.txt", {s: base_us(s) for s in shapes})
            _write_perf(B / f"perf_final_r{rep}.txt", {s: fin_us(s) for s in shapes})
        (B / "test_final.txt").write_text(ok + "  MUL_MAT(type_a=f16,type_b=f32,m=7,n=2,k=64): OK\n2/2 tests passed\n")
        b = phase_b(B, 1024)["verdicts"]
        check("B1 holds at 0.40x", b["B1"]["holds"])
        check("B2 holds and covers the k=640 shape when KMAX*=1024", b["B2"]["holds"] and len(b["B2"]["shapes"]) == 7)
        b512 = phase_b(B, 512)["verdicts"]
        check("with KMAX*=512, only the k=640 shape leaves B2", len(b512["B2"]["shapes"]) == 6
              and not any(s.endswith(", 640)") for s in b512["B2"]["shapes"]))
        check("B3 holds when nothing regresses", b["B3"]["holds"])
        check("B4 holds when final passes base's OK set", b["B4"]["holds"])
        for rep in (1, 2, 3):   # one control regresses by 5 %
            _write_perf(B / f"perf_final_r{rep}.txt",
                        {s: fin_us(s) * (1.05 if s == ("f16", 4096, 1, 4096) else 1) for s in shapes})
        (B / "test_final.txt").write_text(ok + "1/2 tests passed\n")   # a case missing in final counts as not OK
        b = phase_b(B, 1024)["verdicts"]
        check("B3 fails on a 5 % control regression", not b["B3"]["holds"] and "4096" in b["B3"]["worst_shape"])
        check("B4 fails when a base-OK case is missing from final", not b["B4"]["holds"])
    print("self-test:", "FAILED" if fails else "all passed")
    return 1 if fails else 0


if __name__ == "__main__":
    if sys.argv[1:] == ["--self-test"]:
        sys.exit(self_test())
    if sys.argv[1] == "A":
        out = phase_a(sys.argv[2])
    else:
        out = phase_b(sys.argv[2], int(sys.argv[4]))   # KMAX passed explicitly (Deviation 2: registered rule null)
    print(json.dumps(out, indent=1, default=str))
