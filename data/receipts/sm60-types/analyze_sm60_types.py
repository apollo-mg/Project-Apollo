#!/usr/bin/env python3
"""Registered analysis for PREREG_SM60_TYPES.md (committed before any row). T1-T5 exactly as registered.
Inputs: raw/perf_<cfg>_b<block>.txt (test-backend-ops perf console output), raw/decode.jsonl (swift_fn_probe rows,
arm = <FILE>_<cfg><k>), tables/*.tsv. usage: analyze_sm60_types.py [RAWDIR]   (RAWDIR only for the self-test)"""
import json, re, statistics as st, sys
from collections import defaultdict
from pathlib import Path

H = Path(__file__).resolve().parent
RAW = Path(sys.argv[1]) if len(sys.argv) > 1 else H / "raw"
sys.path.insert(0, str(H))
from fn_cases import tensors, N_EXPERT, N_USED  # noqa: E402

BLK = {"f32": (4, 1), "f16": (2, 1), "bf16": (2, 1), "q4_0": (18, 32), "q4_1": (20, 32), "q5_0": (22, 32),
       "q5_1": (24, 32), "q8_0": (34, 32), "q2_K": (84, 256), "q3_K": (110, 256), "q4_K": (144, 256), "q5_K": (176, 256),
       "q6_K": (210, 256), "iq2_xxs": (66, 256), "iq2_xs": (74, 256), "iq2_s": (82, 256), "iq3_xxs": (98, 256),
       "iq3_s": (110, 256), "iq1_s": (50, 256), "iq1_m": (56, 256), "iq4_nl": (18, 32), "iq4_xs": (136, 256),
       "tq1_0": (54, 256), "tq2_0": (66, 256), "mxfp4": (17, 32), "q2_0": (18, 64), "q2_0_g128": (34, 128)}
IQ5 = ["iq2_xxs", "iq2_xs", "iq2_s", "iq3_xxs", "iq3_s"]
LINE = re.compile(r"^\s*(MUL_MAT(?:_ID)?)\((.*?)\):\s+(\d+) runs -\s+([\d.]+) us/run")
FILES = {"UDQ2": "udq2_k_xl.tsv", "GSQB": "gsq_base_iq3xxs.tsv"}


def load_perf():
    T = defaultdict(lambda: defaultdict(list))            # T[cfg][(op, params)] -> [us per block]
    for f in sorted(RAW.glob("perf_*_b*.txt")):
        cfg = f.name.split("_")[1]
        # Deviation 1: stderr ("ggml_cuda_graph_set_enabled: ...") is interleaved into stdout mid-line, between a case
        # name and its timing. Strip those lines, then re-join each case name with its timing.
        text = re.sub(r"ggml_cuda_graph_set_enabled:[^\n]*\n", "", open(f, errors="replace").read())
        for l in text.splitlines():
            m = LINE.match(l)
            if m:
                T[cfg][(m.group(1), m.group(2))].append(float(m.group(4)))
    return {c: {k: st.median(v) for k, v in d.items()} for c, d in T.items()}


def gname(t):                                              # ggml_type_name: lower case, but "q4_K"
    s = t.lower()
    return s[:-2] + "_K" if s.endswith("_k") else s


def dense_key(t, k, m):
    return ("MUL_MAT", f"type_a={gname(t)},type_b=f32,m={m},n=1,k={k},bs=[1,1],nr=[1,1],per=[0,1,2,3],k_v=0,o=1,src_overlap=0")


def moe_key(t, k, m):
    return ("MUL_MAT_ID", f"type_a={gname(t)},type_b=f32,n_mats={N_EXPERT},n_used={N_USED},b=0,m={m},n=1,k={k}")


def stock(P, t, n):
    return P.get(("MUL_MAT", f"type_a={t},type_b=f32,m=4096,n={n},k=14336,bs=[1,1],nr=[1,1],per=[0,1,2,3],k_v=0,o=1,src_overlap=0"))


def gbs(t, us):
    b, e = BLK[t]
    return 4096 * 14336 * b / e / (us * 1e3) if us else None


def file_model(P, table):
    fam, missing = defaultdict(float), []
    for name, t, size, ne in tensors(H / "tables" / table):
        key = moe_key(t, ne[0], ne[1]) if len(ne) == 3 else dense_key(t, ne[0], ne[1])
        us = P.get(key)
        if us is None:
            missing.append(key); continue
        f = re.sub(r"blk\.\d+\.", "", name)
        f = ("hyper-connections" if f.startswith("hc_") else "routers" if f.startswith("ffn_gate_inp")
             else "experts" if "_exps" in f else "shared expert" if "_shexp" in f else "output" if f == "output.weight"
             else "attention/ssm/other")
        fam[f] += us
    return fam, missing


def main():
    P = load_perf()
    res, out = {}, {"cfgs": sorted(P)}
    for cfg in sorted(P):
        print(f"== cfg {cfg}: {len(P[cfg])} cases")
        rows = []
        for t in BLK:
            u1 = stock(P[cfg], t, 1)
            if u1 is None:
                continue
            u4, u512 = stock(P[cfg], t, 4), stock(P[cfg], t, 512)
            rows.append((t, u1, gbs(t, u1), u4, u512))
        for t, u1, g, u4, u512 in sorted(rows, key=lambda r: -(r[2] or 0)):
            print(f"  {t:9s} n=1 {u1:8.1f} us {g:6.1f} GB/s | n=4 {u4 or 0:8.1f} us | n=512 {u512 or 0:9.1f} us")
        out[f"stock_{cfg}"] = {t: {"us1": u1, "gbs1": g, "us4": u4, "us512": u512} for t, u1, g, u4, u512 in rows}
    E, Pc = P.get("E", {}), P.get("P", {})
    if E:
        q8 = gbs("q8_0", stock(E, "q8_0", 1))
        iq = {t: gbs(t, stock(E, t, 1)) for t in IQ5}
        if None not in iq.values():                           # Deviation 1: missing inputs -> pending, not "fails"
            res["T1"] = all(v < 0.7 * q8 for v in iq.values())
        print("T1 inputs: q8_0 %.1f GB/s; " % q8 + ", ".join(f"{t} {v:.1f} ({v / q8:.2f}x)" for t, v in iq.items()))
        hc = []
        for k, m in ((10240, 320), (320, 10240)):
            b, q = E.get(dense_key("BF16", k, m)), E.get(dense_key("Q8_0", k, m))
            hc.append((k, m, b, q, b / q if b and q else None))
            print(f"T3 input: hc k={k} m={m}: BF16 {b} us, Q8_0 {q} us, ratio {b / q if b and q else float('nan'):.2f}")
        if all(r[4] is not None for r in hc):
            res["T3"] = all(r[4] >= 1.5 for r in hc)
    if E and Pc:
        def gain(t):                                           # GB/s gain = time ratio - 1
            a, b = stock(E, t, 1), stock(Pc, t, 1)
            return a / b - 1 if a and b else float("nan")
        g_iq = st.median(gain(t) for t in IQ5); g_q8 = gain("q8_0")
        if g_iq == g_iq and g_q8 == g_q8:
            res["T2"] = g_iq >= 0.10 and g_q8 < 0.05
        print(f"T2 inputs: median IQ gain {g_iq:+.3f}, q8_0 {g_q8:+.3f}, f16 {gain('f16'):+.3f}, bf16 {gain('bf16'):+.3f}")
    dec = defaultdict(list)
    dp = RAW / "decode.jsonl"
    if dp.exists():
        for l in open(dp):
            if l.strip():
                r = json.loads(l); fcfg = r["arm"]; dec[(fcfg.split("_")[0], fcfg.split("_")[1][0])].append(r["predicted_per_second"])
        for k in sorted(dec):
            print(f"decode {k[0]} {k[1]}: n={len(dec[k])} median {st.median(dec[k]):.2f} tok/s")
    models = {}
    for cfg in sorted(P):
        for fk, tb in FILES.items():
            fam, miss = file_model(P[cfg], tb)
            models[(fk, cfg)] = fam
            tot = sum(fam.values()) / 1e3
            meas = 1e3 / st.median(dec[(fk, cfg)]) if dec.get((fk, cfg)) else None
            print(f"model {fk} {cfg}: matmul sum {tot:.2f} ms/token" + (f" of measured {meas:.2f} ms ({tot / meas:.0%})" if meas else "")
                  + (f"  [missing {len(miss)} cases, e.g. {miss[0]}]" if miss else ""))
    if ("GSQB", "E") in models and ("UDQ2", "E") in models:
        a, b = models[("GSQB", "E")], models[("UDQ2", "E")]
        d_pred = (sum(a.values()) - sum(b.values())) / 1e3
        print("  predicted gap by family (GSQ - UD, ms/token): " + ", ".join(f"{f} {(a.get(f, 0) - b.get(f, 0)) / 1e3:+.2f}" for f in sorted(set(a) | set(b))))
        if dec.get(("GSQB", "E")) and dec.get(("UDQ2", "E")):
            d_meas = 1e3 / st.median(dec[("GSQB", "E")]) - 1e3 / st.median(dec[("UDQ2", "E")])
            res["T4"] = d_meas > 0 and d_pred >= 0.5 * d_meas
            print(f"T4 inputs: predicted gap {d_pred:+.2f} ms, measured gap {d_meas:+.2f} ms ({d_pred / d_meas:.0%} explained)")
            out["gap"] = {"pred_ms": d_pred, "meas_ms": d_meas}
    if all(dec.get((f, c)) for f in FILES for c in "EP"):
        g = {f: st.median(dec[(f, "P")]) / st.median(dec[(f, "E")]) - 1 for f in FILES}
        res["T5"] = g["GSQB"] >= g["UDQ2"]
        print(f"T5 inputs: decode gain E->P: GSQ {g['GSQB']:+.3f}, UD {g['UDQ2']:+.3f}")
    for k in ("T1", "T2", "T3", "T4", "T5"):
        print(k, ("HOLDS" if res[k] else "does not hold") if k in res else "pending")
    if len(sys.argv) == 1:
        json.dump({"verdicts": res, **out}, open(H / "RESULT_sm60_types.json", "w"), indent=1, default=str)


if __name__ == "__main__":
    main()
