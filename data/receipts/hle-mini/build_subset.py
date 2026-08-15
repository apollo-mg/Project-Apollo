#!/usr/bin/env python3
"""Build a fixed, reproducible HLE subset -- IDs only, no benchmark content.

Full HLE is 2,500 questions and the official harness wants >=8192 completion
tokens per item to avoid truncation. On this fleet that is 150-450 hours per arm,
so the full set is not runnable here. A fixed subset is, and for measuring
QUANTISATION DELTAS a subset is sufficient: every arm sees identical questions,
so the comparison is internally valid even though the absolute number is not
comparable to published HLE scores. Any result from this MUST be labelled a
subset score, never "our HLE score".

WHY THIS FILE WRITES ONLY IDS:
HLE ships a canary string and asks that its contents never enter training
corpora. Committing 200 questions and their answers to a git repo -- especially
one whose receipts get published -- is precisely how a benchmark gets leaked and
destroyed. So the manifest is a list of question IDs plus metadata, and the
runner re-fetches content from HuggingFace at execution time. Nothing in this
repository contains an HLE question or answer.

Stratification: HLE is 41 % Math (1021/2500). A uniform random draw would inherit
that, leaving too few items per non-math category to say anything per-subject.
This draws PROPORTIONALLY so the aggregate remains a (noisy) estimate of the full
set, and records per-category counts so per-subject noise is visible rather than
implied.

Text-only by default: 342 of 2500 carry images. Qwen 3.8 is multimodal so they
are runnable, but mixing modalities into a quantisation study adds a second
variable (the vision tower is quantised separately, or not at all). Excluded here
and left as a deliberate follow-on.
"""
import argparse, collections, hashlib, json, os, random

CANARY_NOTE = ("HLE content is deliberately NOT stored here. This manifest lists "
               "question ids only; the runner fetches text from HuggingFace.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=200, help="subset size")
    ap.add_argument("--seed", type=int, default=1234)
    ap.add_argument("--include-multimodal", action="store_true")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                  "subset_v1.json"))
    a = ap.parse_args()

    from datasets import load_dataset
    ds = load_dataset("cais/hle", split="test")

    rows = []
    for i in range(len(ds)):
        if not a.include_multimodal and ds[i]["image"]:
            continue
        rows.append({"id": ds[i]["id"], "category": ds[i]["category"],
                     "raw_subject": ds[i]["raw_subject"],
                     "answer_type": ds[i]["answer_type"]})

    by_cat = collections.defaultdict(list)
    for r in rows:
        by_cat[r["category"]].append(r)
    total = len(rows)

    # proportional allocation, largest-remainder so the counts sum exactly to n
    quota = {c: a.n * len(v) / total for c, v in by_cat.items()}
    take = {c: int(q) for c, q in quota.items()}
    rem = sorted(by_cat, key=lambda c: quota[c] - take[c], reverse=True)
    i = 0
    while sum(take.values()) < a.n:
        take[rem[i % len(rem)]] += 1
        i += 1

    rng = random.Random(a.seed)
    picked = []
    for c in sorted(by_cat):                      # sorted => deterministic order
        pool = sorted(by_cat[c], key=lambda r: r["id"])
        picked += rng.sample(pool, min(take[c], len(pool)))
    picked.sort(key=lambda r: r["id"])

    # fingerprint the exact id set, so a later run can prove it used this subset
    digest = hashlib.sha256("\n".join(r["id"] for r in picked).encode()).hexdigest()

    manifest = {
        "name": "hle-mini-v1",
        "note": CANARY_NOTE,
        "source": "cais/hle (test split)",
        "n_requested": a.n, "n_selected": len(picked),
        "seed": a.seed,
        "text_only": not a.include_multimodal,
        "pool_size": total, "full_set_size": len(ds),
        "id_set_sha256": digest,
        "by_category": {c: sum(1 for r in picked if r["category"] == c) for c in sorted(by_cat)},
        "by_answer_type": dict(collections.Counter(r["answer_type"] for r in picked)),
        "ids": [r["id"] for r in picked],
        "meta": {r["id"]: {"category": r["category"], "answer_type": r["answer_type"]}
                 for r in picked},
    }
    json.dump(manifest, open(a.out, "w"), indent=1)
    print(f"pool (text-only={not a.include_multimodal}): {total} of {len(ds)}")
    print(f"selected {len(picked)}  sha256(ids)={digest[:16]}...")
    for c, n in manifest["by_category"].items():
        print(f"  {c:44s} {n:4d}")
    print(f"  answer types: {manifest['by_answer_type']}")
    print(f"-> {a.out}")


if __name__ == "__main__":
    main()
