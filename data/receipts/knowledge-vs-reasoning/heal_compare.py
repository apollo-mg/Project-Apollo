#!/usr/bin/env python3
"""BASE vs PRUNED on identical probes: did pruning move gold's rank, or is this the harness?

Without this the P-HEAL conclusion is unfalsifiable -- 'gold sits at rank 19' means nothing until
you know where it sits in the unpruned model on the same item.
"""
import json, statistics as st

def load(p):
    return {r["id"]: r for r in (json.loads(l) for l in open(p) if l.strip())}

for arm, bf, pf in (("CONFIDENT ERRORS", "base_wrong.jsonl", "heal_wrong.jsonl"),
                    ("REFUSALS",         "base_refusal.jsonl", "heal_refusal.jsonl")):
    B, P = load(bf), load(pf)
    ids = sorted(set(B) & set(P))
    print("=" * 74); print(f"{arm}  (n={len(ids)})"); print("=" * 74)

    # position-0 rank of gold's first token
    for lab, D in (("base", B), ("pruned", P)):
        r = [D[i]["A_gold"]["first_rank"] for i in ids]
        t10 = sum(1 for v in r if v is not None and v <= 10)
        t100 = sum(1 for v in r if v is not None)
        print(f"  A pos-0  {lab:<7} gold in top-10 {t10:3d}/{len(ids)} ({t10/len(ids):4.0%})   "
              f"top-100 {t100:3d} ({t100/len(ids):4.0%})")

    # per-token mean logprob of the forced gold, paired
    pairs = [(B[i]["A_gold"]["mean_logprob"], P[i]["A_gold"]["mean_logprob"]) for i in ids]
    pairs = [(b, p) for b, p in pairs if b is not None and p is not None]
    if pairs:
        d = [p - b for b, p in pairs]
        worse = sum(1 for x in d if x < 0)
        print(f"  A gold mean-logprob, paired (n={len(pairs)}): pruned LOWER in {worse}/{len(pairs)}"
              f" ({worse/len(pairs):.0%}), median delta {st.median(d):+.2f} nats/token")

    # answer-slot measure (wrong arm only)
    sl = [i for i in ids if P[i].get("slot_found") and B[i].get("slot_found")]
    if sl:
        print(f"\n  B answer-slot, {len(sl)} cases with a slot in both arms:")
        print(f"    {'gold':<24}{'base rk':>8}{'pruned rk':>10}{'base mlp':>10}{'pruned mlp':>11}")
        print("    " + "-" * 63)
        dd, bl, pl = [], 0, 0
        for i in sl:
            bg, pg = B[i]["B_gold"], P[i]["B_gold"]
            f = lambda v: f"{v:9.2f}" if v is not None else "        -"
            print(f"    {B[i]['gold'][:23]:<24}{str(bg['first_rank'] or '>100'):>8}"
                  f"{str(pg['first_rank'] or '>100'):>10}{f(bg['mean_logprob'])}"
                  f"{f(pg['mean_logprob']):>11}")
            if bg["mean_logprob"] is not None and pg["mean_logprob"] is not None:
                dd.append(pg["mean_logprob"] - bg["mean_logprob"])
                if pg["mean_logprob"] < bg["mean_logprob"]: pl += 1
                else: bl += 1
        if dd:
            print(f"    pruned gold WORSE than base in {pl}/{len(dd)}; "
                  f"median delta {st.median(dd):+.2f} nats/token")
    print()
