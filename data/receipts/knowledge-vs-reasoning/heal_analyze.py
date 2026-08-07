#!/usr/bin/env python3
"""Score P-HEAL1/P-HEAL2 as registered, then report the answer-slot measure that interprets them."""
import json, statistics as st, sys


def load(p):
    return [json.loads(l) for l in open(p) if l.strip()]


wrong, refus = load(sys.argv[1]), load(sys.argv[2])


def rank_bucket(rows, key="A_gold"):
    r = [x[key]["first_rank"] for x in rows]
    top1 = sum(1 for v in r if v == 1)
    top10 = sum(1 for v in r if v is not None and v <= 10)
    top100 = sum(1 for v in r if v is not None)
    return top1, top10, top100, len(rows)


print("=" * 78)
print("MEASURE A — position-0 rank of gold's first token   [AS PRE-REGISTERED]")
print("=" * 78)
for name, rows, pred in (("wrong (n=77)", wrong, "P-HEAL1"), ("refusal (n=60)", refus, "P-HEAL2")):
    t1, t10, t100, n = rank_bucket(rows)
    print(f"  {name:<16} top-1 {t1:3d} ({t1/n:4.0%})   top-10 {t10:3d} ({t10/n:4.0%})   "
          f"top-100 {t100:3d} ({t100/n:4.0%})")
    print(f"  {'':<16} {pred}: gold in top-10 for >=50% -> "
          f"{'HELD' if t10/n >= 0.5 else 'FALSIFIED'}  (observed {t10/n:.0%})")

print()
print("=" * 78)
print("MEASURE B — at the answer slot, gold vs the answer actually emitted")
print("=" * 78)
sl = [x for x in wrong if x.get("slot_found")]
print(f"  {len(sl)} of {len(wrong)} wrong cases admitted an unambiguous slot ({len(sl)/len(wrong):.0%})")
gw = ew = ties = 0
deltas = []
rows_out = []
for x in sl:
    g, e = x["B_gold"], x["B_emitted"]
    gr, er = g["first_rank"], e["first_rank"]
    gm, em = g["mean_logprob"], e["mean_logprob"]
    if gm is not None and em is not None:
        deltas.append(gm - em)
        if gm > em:
            gw += 1
        elif em > gm:
            ew += 1
        else:
            ties += 1
    rows_out.append((x["gold"], x["emitted_answer"], gr, er, gm, em, g["n_tok"], e["n_tok"]))

print(f"\n  {'gold':<24}{'emitted':<22}{'g.rank':>7}{'e.rank':>7}{'g.mlp':>8}{'e.mlp':>8}{'gtok':>5}{'etok':>5}")
print("  " + "-" * 84)
for gold, em_a, gr, er, gm, emv, gt, et in rows_out:
    f = lambda v: f"{v:7.2f}" if v is not None else "      -"
    print(f"  {gold[:23]:<24}{em_a[:21]:<22}{str(gr or '>100'):>7}{str(er or '>100'):>7}"
          f"{f(gm)}{f(emv)}{gt:>5}{et:>5}")

if deltas:
    print(f"\n  gold mean-logprob HIGHER than emitted: {gw}/{gw+ew+ties}   "
          f"lower: {ew}   tied: {ties}")
    print(f"  delta (gold - emitted) per-token mean logprob: "
          f"median {st.median(deltas):+.2f}, min {min(deltas):+.2f}, max {max(deltas):+.2f} nats")

print()
print("=" * 78)
print("REFUSALS — gold vs \"I don't know\" from an identical prefix (no slot needed)")
print("=" * 78)
gw = ew = 0
deltas = []
for x in refus:
    gm, em = x["A_gold"]["mean_logprob"], x["A_emitted"]["mean_logprob"]
    if gm is None or em is None:
        continue
    deltas.append(gm - em)
    if gm > em:
        gw += 1
    else:
        ew += 1
print(f"  comparable cases: {len(deltas)}/{len(refus)} (rest censored beyond top-100)")
if deltas:
    print(f"  gold preferred over the refusal: {gw}   refusal preferred: {ew}")
    print(f"  delta (gold - refusal) per-token mean logprob: median {st.median(deltas):+.2f} nats, "
          f"min {min(deltas):+.2f}, max {max(deltas):+.2f}")
    near = sum(1 for d in deltas if d > -2)
    print(f"  gold within 2 nats/token of the refusal: {near}/{len(deltas)} ({near/len(deltas):.0%})")

print("\n  sample:")
print(f"  {'gold':<26}{'g.rank':>7}{'g.mlp':>8}{'refusal mlp':>13}")
print("  " + "-" * 56)
for x in refus[:12]:
    gm, em = x["A_gold"]["mean_logprob"], x["A_emitted"]["mean_logprob"]
    f = lambda v: f"{v:7.2f}" if v is not None else "      -"
    print(f"  {x['gold'][:25]:<26}{str(x['A_gold']['first_rank'] or '>100'):>7}{f(gm)}{f(em):>13}")
