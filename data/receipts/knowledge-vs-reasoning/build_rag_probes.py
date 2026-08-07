#!/usr/bin/env python3
"""Build the RAG arm: can the pruned model USE a fact it is handed, on the probes it failed closed-book?

Two conditions, both emitted as ordinary ikp_probes.json records so ikp_run.py / ikp_score.py run
UNCHANGED -- same harness, same grader, same refusal rules as every other leg.

  C1 CLEAN      reference block contains exactly the right entry.
                Tests extraction. A ceiling here is the EXPECTED result and is still informative:
                it would localise the damage to storage/recall, not to instruction-following.

  C2 DISTRACTED reference block contains the right entry plus 3 entries drawn from OTHER probes,
                deterministically ordered. Tests SELECTION under interference, which is what real
                retrieval looks like (k chunks, one relevant). This is the condition that can
                actually separate the arms -- a model whose routing is damaged may fail to pick
                the matching entry even when it is present verbatim.

Entries are Q->A pairs from the probe set itself. Nothing is authored here and no LLM generates
the context, so there is no way for the reference material to be contaminated or to leak style.

Distractors are chosen from the same TIER by a fixed hash of the probe id -- deterministic, no RNG,
and reproducible from this file alone.
"""
import hashlib, json, sys
sys.path.insert(0, "/mnt/TG_2TB/Projects/Apollo/data/receipts/ikp")
from ikp_score import grade

EXCLUDE = {"researcher"}
N_DISTRACT = 3


def load(p):
    o = {}
    for l in open(p):
        l = l.strip()
        if not l:
            continue
        r = json.loads(l)
        if r.get("source_type") in EXCLUDE:
            continue
        o[r["id"]] = r
    return o


base, reap = load(sys.argv[1]), load(sys.argv[2])
ids = sorted(set(base) & set(reap))

# the population under test: probes the BASE answered correctly and the PRUNED then lost
failed, kept = [], []
for i in ids:
    b, p = base[i], reap[i]
    if grade(b["gold"], b.get("response", ""), 25, b.get("finish_reason"))[0] != "CORRECT":
        continue
    vp = grade(p["gold"], p.get("response", ""), 25, p.get("finish_reason"))[0]
    (failed if vp in ("WRONG", "REFUSAL") else kept).append(i)

pool = {}                                    # tier -> [(question, gold)]
for i in ids:
    pool.setdefault(base[i]["tier"], []).append((base[i]["question"], base[i]["gold"]))


def entries(i):
    b = base[i]
    mine = (b["question"], str(b["gold"]).split(";")[0].strip())
    cand = [x for x in pool[b["tier"]] if x[0] != mine[0]]
    h = int(hashlib.sha256(i.encode()).hexdigest(), 16)
    picks = [cand[(h >> (8 * k)) % len(cand)] for k in range(N_DISTRACT)] if cand else []
    # deduplicate while preserving determinism
    seen, out = set(), []
    for q, a in picks:
        if q not in seen:
            seen.add(q)
            out.append((q, a))
    slot = h % (len(out) + 1)                # deterministic position for the correct entry
    out.insert(slot, mine)
    return [mine], out


def block(es, q):
    lines = "\n".join(f"- {eq}  {ea}" for eq, ea in es)
    return f"Reference material:\n{lines}\n\nUsing only the reference material above, answer:\n{q}"


out = []
for i in failed:
    b = base[i]
    c1, c2 = entries(i)
    for cond, es in (("C1", c1), ("C2", c2)):
        out.append({"id": f"{i}__{cond}", "tier": b["tier"], "question": block(es, b["question"]),
                    "answer": b["gold"], "source_type": b.get("source_type"),
                    "domain": b.get("domain")})
# control: probes the pruned arm STILL got right closed-book, under C2.
# If context DEGRADES these, the scaffold is harmful and the whole arm is uninterpretable.
for i in kept:
    b = base[i]
    _, c2 = entries(i)
    out.append({"id": f"{i}__CTRL", "tier": b["tier"], "question": block(c2, b["question"]),
                "answer": b["gold"], "source_type": b.get("source_type"), "domain": b.get("domain")})

json.dump(out, open(sys.argv[3], "w"), ensure_ascii=False, indent=1)
print(f"population: {len(failed)} lost probes, {len(kept)} retained (control)")
print(f"emitted {len(out)} records -> {sys.argv[3]}")
print(f"  C1 {sum(1 for r in out if r['id'].endswith('C1'))}, "
      f"C2 {sum(1 for r in out if r['id'].endswith('C2'))}, "
      f"CTRL {sum(1 for r in out if r['id'].endswith('CTRL'))}")
print("\n--- sample C2 ---")
print([r for r in out if r["id"].endswith("C2")][0]["question"])
