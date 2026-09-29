#!/usr/bin/env python3
"""Registered analysis for PREREG_HC_Q8.md (committed before any row). H1-H4 exactly as registered.
usage: analyze_hc_q8.py [RAWHC RAWK]   (dirs only for the self-test; default raw_hc/ and raw/)"""
import json, re, statistics as st, sys
from collections import defaultdict
from pathlib import Path

H = Path(__file__).resolve().parent
RAWHC = Path(sys.argv[1]) if len(sys.argv) > 2 else H / "raw_hc"
RAWK = Path(sys.argv[2]) if len(sys.argv) > 2 else H / "raw"
LINE = re.compile(r"^\s*MUL_MAT\(type_a=(\w+),type_b=f32,m=(\d+),n=1,k=(\d+),.*?\):\s+(\d+) runs -\s+([\d.]+) us/run")


def kernels():
    T = defaultdict(list)
    for f in sorted(RAWHC.glob("perf_hc_E_r*.txt")):
        text = re.sub(r"ggml_cuda_graph_set_enabled:[^\n]*\n", "", f.read_text(errors="replace"))
        for l in text.splitlines():
            m = LINE.match(l)
            if m:
                T[(m.group(1), int(m.group(2)), int(m.group(3)))].append(float(m.group(5)))
    return {k: st.median(v) for k, v in T.items()}


def decode(path, arms):
    d = defaultdict(list)
    if path.exists():
        for l in open(path):
            if l.strip():
                r = json.loads(l)
                for a in arms:
                    if r["arm"] == a or r["arm"].startswith(a + "_E"):
                        d[a].append(r)
    return d


def main():
    res = {}
    K = kernels()
    for (t, m, k), us in sorted(K.items()):
        print(f"kernel {t:5s} m={m:5d} k={k:5d}: {us:7.2f} us")
    f16, q8 = K.get(("f16", 10240, 320)), K.get(("q8_0", 10240, 320))
    if f16 and q8:
        res["H3"] = f16 >= 2 * q8
        print(f"H3 input: F16 {f16:.2f} us vs Q8_0 {q8:.2f} us at k=320 m=10240 ({f16 / q8:.2f}x)")
    D = decode(RAWHC / "decode.jsonl", ["HCQ8", "GSQB"])
    U = decode(RAWK / "decode.jsonl", ["UDQ2"])
    med = {a: st.median(r["predicted_per_second"] for r in v) for a, v in {**D, **U}.items() if v}
    for a, v in med.items():
        print(f"decode {a}: n={len({**D, **U}[a])} median {v:.2f} tok/s")
    if "HCQ8" in med and "GSQB" in med:
        res["H1"] = med["HCQ8"] >= 1.07 * med["GSQB"]
        print(f"H1 input: HCQ8 / GSQB = {med['HCQ8'] / med['GSQB']:.3f}")
    if "HCQ8" in med and "UDQ2" in med:
        res["H2"] = abs(med["HCQ8"] / med["UDQ2"] - 1) <= 0.03
        print(f"H2 input: HCQ8 / UDQ2 = {med['HCQ8'] / med['UDQ2']:.3f}")
    if D.get("HCQ8") and D.get("GSQB"):
        a = {(r["rep"], r["prompt"]): r["content"] or "" for r in D["HCQ8"]}
        b = {(r["rep"], r["prompt"]): r["content"] or "" for r in D["GSQB"]}
        same, first = 0, []
        for key in sorted(set(a) & set(b)):
            x, y = a[key], b[key]
            if x == y:
                same += 1
            else:
                first.append(next((i for i, (p, q) in enumerate(zip(x, y)) if p != q), min(len(x), len(y))))
        print(f"greedy agreement: {same}/{len(set(a) & set(b))} identical; first difference at chars {sorted(first)}")
    kf = RAWHC / "kld_hcq8.txt"
    if kf.exists():
        t = kf.read_text(errors="replace")
        m = re.search(r"Mean\s+KLD:\s+([\d.]+)", t); p = re.search(r"Same top p:\s+([\d.]+)", t)
        if m:
            res["H4"] = float(m.group(1)) < 0.01
            print(f"H4 input: mean KLD {float(m.group(1)):.5f}" + (f", same top p {p.group(1)} %" if p else ""))
    for k in ("H1", "H2", "H3", "H4"):
        print(k, ("HOLDS" if res[k] else "does not hold") if k in res else "pending")
    if len(sys.argv) == 1:
        json.dump({"verdicts": res, "decode_median": med, "kernels": {f"{t}|{m}|{k}": v for (t, m, k), v in K.items()}},
                  open(H / "RESULT_hc_q8.json", "w"), indent=1)


if __name__ == "__main__":
    main()
