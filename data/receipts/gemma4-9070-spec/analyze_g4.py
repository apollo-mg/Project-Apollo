#!/usr/bin/env python3
"""PREREG_GEMMA4_9070_SPEED.md: tabulate every arm from runs/lmx_<ARM>.json (LocalMaxxing CLI output) and
runs/server_<ARM>.log (llama-server's per-request draft acceptance). Writes RESULT_g4.json; prints a markdown table."""
import json, re, statistics, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
ORDER = ["B0", "D8", "D4", "D8n1", "D8n2", "D8n4", "K8", "UB256", "UB1024", "BEST_r2", "BEST_r3", "Q0", "Q0_B0", "CR0", "SUB1", "C_B0", "C_D8n2_r1", "C_D8n2_r2", "C_D8n2_r3", "C_D8n3", "C_D8n2_noproxy", "R_B0", "R_D8n2_r1", "R_D8n2_r2", "R_D8n2_r3", "R_D8n3"]
ACC = re.compile(r"draft acceptance = ([\d.]+) \(\s*(\d+) accepted /\s*(\d+) generated\), mean len =\s*([\d.]+)")


def arm(name):
    j = json.loads((RUNS / f"lmx_{name}.json").read_text())
    acc = [tuple(map(float, m.groups())) for m in ACC.finditer((RUNS / f"server_{name}.log").read_text())]
    timed = acc[-3:] if len(acc) >= 4 else acc          # the first request is LMX's untimed warmup
    return {"arm": name, "tokSOut": j["tokSOut"], "samples": [s["tokSOut"] for s in j["samples"]],
            "ttftMs": j["ttftMs"], "tokSPrefill_est": j.get("tokSPrefill"), "promptTokens": j["promptTokens"],
            "outputTokens": j["outputTokens"], "spec": j.get("engineFlags", {}).get("specDecoding", False),
            "accept": [a[0] for a in timed], "mean_len": [a[3] for a in timed]}


def main():
    rows = [arm(a) for a in ORDER if (RUNS / f"lmx_{a}.json").exists()]
    best = [r["tokSOut"] for r in rows if r["arm"] in ("D8n2", "BEST_r2", "BEST_r3")]
    out = {"rows": rows, "best_config_medians": best, "best_median_of_medians": statistics.median(best) if best else None,
           "tom_reference": 85.3,
           "verdicts": {"P1_B0_55_62": next((55 <= r["tokSOut"] <= 62 for r in rows if r["arm"] == "B0"), None),
                        "P2_drafter_1.25x": (max(r["tokSOut"] for r in rows if r["arm"].startswith("D8"))
                                             / next(r["tokSOut"] for r in rows if r["arm"] == "B0")) >= 1.25,
                        "P3_best_ge_85.3": (statistics.median(best) >= 85.3) if best else None,
                        "P4_Q0_faster": next((r["tokSOut"] for r in rows if r["arm"] == "Q0"), 0) > (statistics.median(best) if best else 1e9)}}
    (HERE / "RESULT_g4.json").write_text(json.dumps(out, indent=1))
    print("| arm | tok/s out (median) | samples | acceptance (timed) | mean len | TTFT ms | prompt |")
    print("|---|---:|---|---|---|---:|---:|")
    for r in rows:
        print(f"| {r['arm']} | {r['tokSOut']} | {', '.join(map(str, r['samples']))} | "
              f"{', '.join(f'{a:.2f}' for a in r['accept']) or '-'} | {', '.join(f'{m:.2f}' for m in r['mean_len']) or '-'} | "
              f"{r['ttftMs']:.0f} | {r['promptTokens']} |")
    print("\nbest config medians:", best, "-> median", out["best_median_of_medians"]); print("verdicts:", out["verdicts"])


if __name__ == "__main__":
    sys.exit(main())
