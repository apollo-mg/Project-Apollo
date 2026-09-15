#!/usr/bin/env python3
"""EXPLORATORY placement analysis for qwen4exp Stage 5. NOT a preregistered prediction.

Usage: analyze_flashnext_placement.py ~/flashnext_res/results.jsonl

**Written 2026-09-14 21:02, mid-run, with only D-08 and D-16 measured and the other eight rungs not
yet collected.** Committed before the data exists specifically so the method cannot be fitted to it.
Anything this prints is a hypothesis for a later prereg to test, never a result of this stage.

The question. D-08 came in 3.9-7.0% under Stage 4 and had landed 81% of its host memory on node 1;
D-16 reproduced Stage 4 to within 1% and had landed 82% on node 0. Two points and a story. Three
mechanisms predict different things about the ten-rung ladder, so they can be separated:

  H1  DMA locality. The CPU backend computes expert outputs and they are copied to the consuming GPU.
      GPU0/GPU1 are on node 0, GPU2/GPU3 on node 1 (verified via sysfs numa_node). `-ncmoe N` spills
      the first N layers, and at ~12 layers per card every consumer is on node 0 until rung ~24.
      PREDICTS: deviation tracks NODE-0 SHARE, and the relationship weakens above rung 24.

  H2  Thread locality. `--numa distribute` splits threads thread_n % n_nodes, i.e. 50/50, so average
      thread-to-memory locality depends on |I| but NOT on which node dominates.
      PREDICTS: deviation tracks |I|, sign-blind.

  H3  Lottery. Placement is uncontrolled and decode variance is just variance.
      PREDICTS: no correlation with either, and residual scatter of the observed size.

H1 and H2 make opposite predictions about a rung that is heavily imbalanced TOWARD node 0: H1 says
fast, H2 says slow. That is the discriminating case.

Caveat that applies to every number below: one observation per rung, and Stage 4 recorded no placement
at all, so the "deviation" baseline carries its own unmeasured placement. Correlation over ten points
with no repeats is a direction to investigate, not a finding.
"""
import json, math, statistics, sys

STAGE4 = {8:  {500: 17.60, 1800: 17.39, 3600: 15.84},
          16: {500: 13.57, 1800: 13.60, 3600: 12.84},
          32: {500: 10.75, 1800: 10.72, 3600: 10.29}}
NODE0_CONSUMERS_UP_TO = 24   # rungs at or below this spill only into node-0 GPUs (12 layers/card)


def pearson(xs, ys):
    if len(xs) < 3:
        return None
    mx, my = statistics.mean(xs), statistics.mean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    return num / (dx * dy) if dx and dy else None


def main(path):
    rows = [json.loads(l) for l in open(path) if l.strip()]
    req, place, done = {}, {}, set()
    for r in rows:
        if r.get("stage") == "req" and r.get("tg_tps"):
            req.setdefault((r["arm"], r["len"]), []).append(r["tg_tps"])
        elif r.get("stage") == "arm_done":
            done.add(r["arm"])
            if r.get("placement_after_run"):
                place[r["arm"]] = r["placement_after_run"]

    recs = []
    for a in sorted(x for x in done if x.startswith("D-")):
        n = int(a.split("-")[1])
        pl = place.get(a) or {}
        tot = pl.get("total_mib") or {}
        t0, t1 = tot.get("0", 0.0), tot.get("1", 0.0)
        if not (t0 + t1):
            continue
        share0 = t0 / (t0 + t1)
        med = {L: statistics.median(v) for L, v in ((L, req.get((a, L), [])) for L in (500, 1800, 3600)) if v}
        dev = None
        if n in STAGE4 and med:
            ds = [(med[L] - STAGE4[n][L]) / STAGE4[n][L] for L in med if L in STAGE4[n]]
            dev = statistics.mean(ds) if ds else None
        recs.append({"arm": a, "n": n, "share0": share0, "I": pl.get("imbalance"),
                     "dec1800": med.get(1800), "dev": dev, "host_mib": t0 + t1})

    print("## Placement by rung (exploratory, not preregistered)\n")
    print("| arm | -ncmoe | host MiB | node0 share | I | decode@1800 | vs Stage 4 | consumers |")
    print("|---|---:|---:|---:|---:|---:|---:|---|")
    for r in recs:
        where = "node 0 only" if r["n"] <= NODE0_CONSUMERS_UP_TO else "both nodes"
        dev = f"{r['dev'] * 100:+.1f}%" if r["dev"] is not None else "—"
        print(f"| {r['arm']} | {r['n']} | {r['host_mib']:,.0f} | **{r['share0'] * 100:.0f}%** | "
              f"{r['I']:.3f} | {r['dec1800'] or float('nan'):.2f} | {dev} | {where} |")

    # H1 vs H2 on the shared rungs, where a Stage 4 baseline exists.
    withdev = [r for r in recs if r["dev"] is not None]
    if len(withdev) >= 3:
        c1 = pearson([r["share0"] for r in withdev], [r["dev"] for r in withdev])
        c2 = pearson([abs(r["I"]) for r in withdev], [r["dev"] for r in withdev])
        print(f"\n- **H1** deviation vs node-0 share: r = {c1:+.3f} (n={len(withdev)})" if c1 is not None
              else "\n- **H1**: too few points")
        print(f"- **H2** deviation vs |I|: r = {c2:+.3f}" if c2 is not None else "- **H2**: too few points")
        print("- only three rungs have a Stage 4 baseline, so these r values are indicative at best")
    else:
        print("\n- **H1/H2**: not enough rungs with a Stage 4 baseline yet")

    # Within-ladder: does node-0 share predict decode once the rung's own effect is removed?
    shallow = [r for r in recs if r["n"] <= NODE0_CONSUMERS_UP_TO and r["dec1800"]]
    if len(shallow) >= 4:
        # regress decode on rung, then correlate the residual with node-0 share
        xs = [r["n"] for r in shallow]
        ys = [r["dec1800"] for r in shallow]
        mx, my = statistics.mean(xs), statistics.mean(ys)
        sxx = sum((x - mx) ** 2 for x in xs)
        slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx if sxx else 0.0
        resid = [y - (my + slope * (x - mx)) for x, y in zip(xs, ys)]
        c = pearson([r["share0"] for r in shallow], resid)
        print(f"\n- **within-ladder, shallow rungs only** (consumers all on node 0, n={len(shallow)}): "
              f"residual decode vs node-0 share r = {c:+.3f}" if c is not None else "")
        print("    - H1 predicts a POSITIVE r here (more memory on node 0 → faster than the rung trend)")
        print("    - H2 predicts none, since it is sign-blind; H3 predicts none")
    print("\n*Exploratory. One run per rung, no repeats, and the Stage 4 baseline has unmeasured "
          "placement of its own. A later prereg should fix a rung and vary placement deliberately.*")


if __name__ == "__main__":
    main(sys.argv[1])
