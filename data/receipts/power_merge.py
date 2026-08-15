#!/usr/bin/env python3
"""Turn a powerlog + arm markers into per-arm watts, and flag cap saturation.

Companion to powerlog.sh. Emits a VERDICT, not a dataset (see verdict.py): one
line per arm, detail to a sidecar.

Reports peak, mean and p95 rather than peak alone. Peak catches a single spike
that may be another process; p95 is what the arm actually sustained, and the two
disagreeing is itself informative.

`at_cap_pct` is the fraction of samples within 2 % of the recorded power limit.
An arm sitting at the cap is throttled: its throughput is a statement about the
cap, not about the code, and optimising it further buys nothing. That distinction
is invisible in a t/s column and is the main reason this exists.

Usage: power_merge.py <powerlog> [--out FILE]
"""
import argparse, collections, json, os, statistics, sys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("log")
    ap.add_argument("--out")
    a = ap.parse_args()

    samples = collections.defaultdict(list)   # dev -> [(t, w)]
    marks = []                                 # (t, tag, kind)
    cap = None
    for line in open(a.log):
        line = line.strip()
        if not line:
            continue
        if line.startswith("#"):
            if "power_limit_w=" in line:
                try:
                    cap = max(float(x) for x in line.split("power_limit_w=")[1].split(",") if x.strip())
                except Exception:
                    pass
            continue
        if line.startswith("MARK"):
            p = line.split()
            if len(p) >= 4:
                marks.append((int(p[1]), p[2], p[3]))
            continue
        p = line.split(",")
        if len(p) == 3:
            try:
                samples[p[1]].append((int(p[0]), float(p[2])))
            except ValueError:
                pass

    if not samples:
        print(f"no power samples in {a.log}"); sys.exit(1)

    windows = {}
    open_t = {}
    for t, tag, kind in marks:
        if kind == "start":
            open_t[tag] = t
        elif kind == "end" and tag in open_t:
            windows[tag] = (open_t.pop(tag), t)
    if open_t:
        print(f"  note: {len(open_t)} arm(s) never closed: {', '.join(open_t)}")

    if not windows:
        allw = [w for v in samples.values() for _, w in v]
        print(f"no arm markers; whole log: peak {max(allw):.0f} W  mean {statistics.mean(allw):.0f} W  "
              f"n={len(allw)}")
        return

    print(f"{'arm':<20} {'peak W':>7} {'p95 W':>7} {'mean W':>7} {'at cap':>7}  n")
    detail = {}
    for tag, (t0, t1) in sorted(windows.items(), key=lambda kv: kv[1][0]):
        per_dev = {}
        for dev, v in samples.items():
            w = [x for t, x in v if t0 <= t <= t1]
            if w:
                per_dev[dev] = w
        if not per_dev:
            print(f"{tag:<20} {'—':>7} (no samples in window)"); continue
        # sum across devices at each timestamp = board-level draw for multi-GPU nodes
        allw = [x for v in per_dev.values() for x in v]
        srt = sorted(allw)
        p95 = srt[min(len(srt) - 1, int(0.95 * len(srt)))]
        atcap = (100 * sum(1 for x in allw if cap and x >= 0.98 * cap) / len(allw)) if cap else None
        print(f"{tag:<20} {max(allw):7.0f} {p95:7.0f} {statistics.mean(allw):7.0f} "
              f"{(f'{atcap:.0f}%' if atcap is not None else '—'):>7}  {len(allw)}")
        detail[tag] = {"peak": max(allw), "p95": p95, "mean": statistics.mean(allw),
                       "n": len(allw), "seconds": t1 - t0, "at_cap_pct": atcap,
                       "per_device": {d: {"peak": max(v), "mean": statistics.mean(v)}
                                      for d, v in per_dev.items()}}
    if cap:
        print(f"\npower limit {cap:.0f} W — 'at cap' is the share of samples within 2 % of it")
        if any(d.get("at_cap_pct") and d["at_cap_pct"] > 20 for d in detail.values()):
            print("  *** an arm is throttled; its t/s describes the cap, not the code ***")
    out = a.out or (os.path.splitext(a.log)[0] + "_power.json")
    json.dump(detail, open(out, "w"), indent=1)
    print(f"detail -> {out}")


if __name__ == "__main__":
    main()
