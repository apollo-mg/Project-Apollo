#!/usr/bin/env python3
"""Build a NESTED screening subset -- a fast triage gate, not a score.

Purpose: decide in ~1 hour on the 9070 XT whether a model is worth a full
subset run at all. This is the cheap gate in front of the expensive test.

THE TRAP THIS IS DESIGNED AROUND. `qwen38-lowbit/RESULT_2x2.md` recorded a test
that could not have measured what it set out to: eight prompts, 8/8 in all four
cells, zero discriminating power. A 50-question HLE screen has the mirror-image
failure available -- HLE is hard enough that local quantised models may score 0-2
out of 50, in which case accuracy separates nothing and the screen is a
30-question way of learning nothing.

So the screen is deliberately NOT an accuracy instrument. It reports readiness:

  answer-parse rate  -- did the model emit HLE's required output format at all?
  truncation rate    -- did it cap-death inside the think block? (battle16gb
                        Finding 5: a 25 pp gap that was a stopping-rule failure,
                        not an answering failure)
  confidence sanity  -- did it produce a usable confidence, and is it absurd?
  token spend        -- median tokens per question, which sets the cost of the
                        full run and is the number the screen exists to provide
  accuracy           -- reported, but expected to floor, and NOT the gate

A model that answers 4 % with well-formed, non-truncated, sanely-calibrated
output is worth a full run. A model that loops, truncates 80 % of the time and
never emits an `Exact Answer:` line is not -- regardless of which of them scores
one point higher on 50 items.

NESTED BY CONSTRUCTION: every screen id is drawn from subset_v1's id list, so a
screen run is a strict prefix of the work a full run would do, results are
directly comparable, and nothing is wasted if the model passes the gate.

UPGRADE PATH: once several models have full-subset results, the screen should be
RE-SELECTED by measured discrimination -- keeping items that some models get
right and others do not, discarding items everyone fails or everyone passes.
That is not possible yet with zero result files, so v1 stratifies proportionally.
Bump the version when that reselection happens; do not silently redefine `screen_v1`.
"""
import argparse, collections, hashlib, json, os, random

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=50,
                    help="50 targets ~1h on RX 9070 XT with MTP on; PROVISIONAL "
                         "until a pilot measures tokens/question")
    ap.add_argument("--seed", type=int, default=99)
    ap.add_argument("--parent", default=os.path.join(HERE, "subset_v1.json"))
    ap.add_argument("--out", default=os.path.join(HERE, "screen_v1.json"))
    a = ap.parse_args()

    parent = json.load(open(a.parent))
    meta = parent["meta"]
    by_cat = collections.defaultdict(list)
    for qid in parent["ids"]:
        by_cat[meta[qid]["category"]].append(qid)

    total = len(parent["ids"])
    quota = {c: a.n * len(v) / total for c, v in by_cat.items()}
    take = {c: int(q) for c, q in quota.items()}
    rem = sorted(by_cat, key=lambda c: quota[c] - take[c], reverse=True)
    i = 0
    while sum(take.values()) < a.n:
        take[rem[i % len(rem)]] += 1
        i += 1

    rng = random.Random(a.seed)
    picked = []
    for c in sorted(by_cat):
        picked += rng.sample(sorted(by_cat[c]), min(take[c], len(by_cat[c])))
    picked.sort()

    assert set(picked) <= set(parent["ids"]), "screen must be nested in the parent subset"

    at = collections.Counter(meta[q]["answer_type"] for q in picked)
    out = {
        "name": "hle-screen-v1",
        "note": parent["note"],
        "purpose": "triage gate: is this model worth a full subset run",
        "nested_in": parent["name"],
        "parent_id_set_sha256": parent["id_set_sha256"],
        "n_selected": len(picked), "seed": a.seed,
        "id_set_sha256": hashlib.sha256("\n".join(picked).encode()).hexdigest(),
        "by_category": {c: sum(1 for q in picked if meta[q]["category"] == c)
                        for c in sorted(by_cat)},
        "by_answer_type": dict(at),
        "gate_is_not_accuracy": (
            "Accuracy on 50 HLE items is expected to floor near zero for local "
            "quantised models and is NOT the gate. Gate on parse rate, truncation "
            "rate and token spend. Report MC and exactMatch accuracy separately: "
            "multipleChoice carries a guessing baseline and exactMatch does not, "
            "so pooling them makes a guessing model look partially competent."),
        "ids": picked,
        "meta": {q: meta[q] for q in picked},
    }
    json.dump(out, open(a.out, "w"), indent=1)
    print(f"screen {out['name']}  n={len(picked)}  nested in {parent['name']}")
    print(f"  id_sha256 {out['id_set_sha256'][:16]}")
    for c, n in out["by_category"].items():
        print(f"  {c:44s} {n:3d}")
    print(f"  answer types: {dict(at)}")
    small = [c for c, n in out["by_category"].items() if n < 3]
    if small:
        print(f"  NOTE: per-category accuracy is meaningless for {', '.join(small)} "
              f"(n<3). Aggregate only.")
    print(f"-> {a.out}")


if __name__ == "__main__":
    main()
