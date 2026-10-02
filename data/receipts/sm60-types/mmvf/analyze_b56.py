#!/usr/bin/env python3
"""PREREG_MMVF_SHORTROW.md B5/B6 (Deviation 3). usage: analyze_b56.py RAW_B56_DIR | --self-test
B5: median pass-2 predicted_per_second pooled per build (base_s1+base_s2 vs final_s1+final_s2), final/base >= 1.07.
B6: mean KLD(final vs base) at -ub 1 < 0.001, only if exercised (final prompt-eval ms/token <= 0.98x base's)."""
import json, re, statistics, sys, tempfile
from pathlib import Path

KLD = re.compile(r"Mean\s+KLD:\s+([\d.eE+-]+)")
TOP = re.compile(r"Same top p:\s+([\d.]+)")
PEVAL = re.compile(r"prompt eval time =\s+([\d.]+) ms /\s+(\d+) tokens")


def load_rows(p):
    return [json.loads(l) for l in Path(p).read_text().splitlines() if l.strip()]


def b5(rows):
    def med(build, rep):
        v = [r["predicted_per_second"] for r in rows if r["arm"].startswith(build + "_") and r["rep"] == rep]
        return statistics.median(v), len(v)
    (fb, nf), (bb, nb) = med("final", 2), med("base", 2)
    per = {}
    for tag in sorted({r["arm"] for r in rows}):
        for rep in (1, 2):
            v = [r["predicted_per_second"] for r in rows if r["arm"] == tag and r["rep"] == rep]
            per[f"{tag}_pass{rep}"] = round(statistics.median(v), 3) if v else None
    # greedy agreement, pass 2: same prompt, first server of each build
    def text(tag, pid):
        return next((r["content"] for r in rows if r["arm"] == tag and r["rep"] == 2 and r["prompt"] == pid), None)
    pids = sorted({r["prompt"] for r in rows})
    same = sum(text("base_s1", p) == text("final_s1", p) for p in pids)
    within_base = sum(text("base_s1", p) == text("base_s2", p) for p in pids)
    within_final = sum(text("final_s1", p) == text("final_s2", p) for p in pids)
    ratio = fb / bb
    return {"holds": ratio >= 1.07 and nf == 12 and nb == 12, "ratio": ratio, "final_tok_s": fb, "base_tok_s": bb,
            "n": {"final": nf, "base": nb}, "medians": per,
            "greedy_identical_base_vs_final": f"{same}/{len(pids)}",
            "within_build_repeat": {"base": f"{within_base}/{len(pids)}", "final": f"{within_final}/{len(pids)}"}}


def ms_per_tok(txt):
    m = PEVAL.search(txt)
    return float(m.group(1)) / int(m.group(2)) if m else None


def b6(raw):
    raw = Path(raw)
    base, selft, fin = [(raw / f).read_text(errors="replace") for f in ("kld_base.txt", "kld_self.txt", "kld_final.txt")]
    kf, ks = KLD.search(fin), KLD.search(selft)
    tb, tf = ms_per_tok(base), ms_per_tok(fin)
    exercised = tb is not None and tf is not None and tf <= 0.98 * tb
    kld = float(kf.group(1)) if kf else None
    return {"holds": bool(exercised and kld is not None and kld < 0.001),
            "inconclusive": not exercised, "mean_kld_final": kld, "mean_kld_self": float(ks.group(1)) if ks else None,
            "same_top_final": (TOP.search(fin) or [None, None])[1], "same_top_self": (TOP.search(selft) or [None, None])[1],
            "ms_per_tok": {"base": tb, "final": tf, "ratio": (tf / tb) if tb and tf else None}}


def self_test():
    fails = []
    def check(name, cond):
        print(("PASS  " if cond else "FAIL  ") + name); fails.append(name) if not cond else None
    with tempfile.TemporaryDirectory() as d:
        d = Path(d); rows = []
        for tag, tps in (("base_s1", 18.8), ("final_s1", 20.9), ("final_s2", 20.95), ("base_s2", 18.85)):
            for rep in (1, 2):
                for pid in ("a", "b", "c", "d", "e", "f"):
                    rows.append({"arm": tag, "rep": rep, "prompt": pid, "predicted_per_second": tps - (1.5 if rep == 1 else 0),
                                 "content": pid + ("X" if (tag.startswith("final") and pid == "f") else "")})
        r = b5(rows)
        check("B5 pools pass 2 per build (12 each)", r["n"] == {"final": 12, "base": 12})
        check("B5 ratio 20.925/18.825 holds", r["holds"] and abs(r["ratio"] - 20.925 / 18.825) < 1e-9)
        check("pass 1 rows do not enter B5", abs(r["base_tok_s"] - 18.825) < 1e-9)
        check("greedy agreement counts a differing prompt", r["greedy_identical_base_vs_final"] == "5/6")
        check("B5 fails at 1.05x", not b5([dict(x, predicted_per_second=x["predicted_per_second"] * (1.05 * 18.825 / 20.925)
                                            if x["arm"].startswith("final") else x["predicted_per_second"]) for x in rows])["holds"])
        tail = "Mean    KLD:   {k}\nSame top p: 99.9 ± 0.1 %\nllama_perf_context_print: prompt eval time =  {ms} ms /  8192 tokens\n"
        (d / "kld_base.txt").write_text("Final estimate: PPL = 6.1\n" + "llama_perf_context_print: prompt eval time =  400000.00 ms /  8192 tokens\n")
        (d / "kld_self.txt").write_text(tail.format(k="0.000000", ms="400100.00"))
        (d / "kld_final.txt").write_text(tail.format(k="0.000012", ms="360000.00"))
        r = b6(d)
        check("B6 holds when exercised and KLD tiny", r["holds"] and r["mean_kld_final"] == 0.000012)
        (d / "kld_final.txt").write_text(tail.format(k="0.000012", ms="396000.00"))
        r = b6(d)
        check("B6 inconclusive when final is not faster (kernel not shown to run)", not r["holds"] and r["inconclusive"])
        (d / "kld_final.txt").write_text(tail.format(k="0.0021", ms="360000.00"))
        check("B6 fails at KLD 0.0021", not b6(d)["holds"])
    print("self-test:", "FAILED" if fails else "all passed")
    return 1 if fails else 0


if __name__ == "__main__":
    if sys.argv[1:] == ["--self-test"]:
        sys.exit(self_test())
    raw = Path(sys.argv[1]); out = {}
    if (raw / "decode.jsonl").exists():
        out["B5"] = b5(load_rows(raw / "decode.jsonl"))
    if (raw / "kld_final.txt").exists():
        out["B6"] = b6(raw)
    print(json.dumps(out, indent=1))
