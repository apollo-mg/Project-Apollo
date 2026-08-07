#!/usr/bin/env python3
"""C4 (provenance) and C5 (foreign contradiction) — mechanism and fixability of the C3 collapse.

C3 established: given two competing entries for one question, the pruned arm answers by POSITION
(59.1 pp order sensitivity) while the base arm answers by CONTENT (6.6 pp). A free control on the
C2 data showed this is NOT a general primacy bias -- with one correct entry among unrelated
distractors the pruned arm scored 100/100/99.1/100 % across all four positions. The collapse is
specific to CONTRADICTION.

Two questions follow, and each is one cheap arm:

C4  IS IT FIXABLE?  Same contradiction, but each entry carries a provenance tag. If a source cue
    lets the pruned model override position, the practical fix is trivial (label and order your
    chunks). Two cells, deliberately opposed:
      C4a  gold SECOND + authoritative tag on GOLD    -- can provenance BEAT position?
      C4b  gold FIRST  + authoritative tag on CONFAB   -- can provenance DRAG IT OFF the truth?
    C4b is the control that stops C4a being read as mere tag-following: a model that blindly
    follows tags scores high on C4a and LOW on C4b.

C5  IS IT ABOUT ITS OWN PRIOR?  Same two-entry contradiction, but the wrong entry is another
    probe's GOLD from the same domain -- type-appropriate, plausible, and NOT this model's own
    confabulation. If the order sensitivity persists, the C3 effect is general contradiction-
    adjudication failure and has nothing to do with the model believing its own answer.
    Both orders, as in C3.
"""
import hashlib, json, re, sys
sys.path.insert(0, "/mnt/TG_2TB/Projects/Apollo/data/receipts/ikp")
from ikp_score import grade

EXCLUDE = {"researcher"}
ARTIFACTS = {"Michael Faraday", "Johannes Kepler", "Wolfgang Pauli", "Warsaw", "East African Rift"}
MAXW = 8
STRONG = "Encyclopaedia Britannica, 2026 edition"
WEAK = "unverified forum post"

BOLD = re.compile(r"\*\*(.+?)\*\*")
CONN = re.compile(r"\b(?:is|are|was|were|by)\s+")
PART = re.compile(r"^(?:founded|written|completed|published|designed|discovered|built|"
                  r"established|sculpted|painted|composed|invented|formulated|launched)\s+"
                  r"(?:in|by|on|at)\s+", re.I)


def bare_answer(resp):
    resp = resp.strip()
    m = list(BOLD.finditer(resp))
    if len(m) == 1:
        return m[0].group(1).strip()
    if len(resp.split()) <= 3:
        return resp.rstrip(".")
    first = re.split(r"(?<=[.!?])\s", resp)[0].rstrip(".!?")
    ms = list(CONN.finditer(first))
    if not ms:
        return None
    tail = first[ms[-1].end():].strip()
    if not tail or len(tail.split()) > 6 or any(c in tail for c in '"\'()*[]'):
        return None
    return PART.sub("", tail).strip() or None


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


def blk(q, e1, e2):
    return (f"Reference material:\n- {e1[0]}{q}  {e1[1]}\n- {e2[0]}{q}  {e2[1]}\n\n"
            f"Using only the reference material above, answer:\n{q}")


base, reap = load(sys.argv[1]), load(sys.argv[2])
ids = sorted(set(base) & set(reap))
by_domain = {}
for i in ids:
    by_domain.setdefault(base[i].get("domain") or "?", []).append(
        str(base[i]["gold"]).split(";")[0].strip())

out = []
for i in ids:
    b, p = base[i], reap[i]
    if grade(b["gold"], b.get("response", ""), 25, b.get("finish_reason"))[0] != "CORRECT":
        continue
    if grade(p["gold"], p.get("response", ""), 25, p.get("finish_reason"))[0] != "WRONG":
        continue
    if b["gold"] in ARTIFACTS:
        continue
    conf = bare_answer(p.get("response") or "")
    gold = str(b["gold"]).split(";")[0].strip()
    if not conf or len(conf.split()) > MAXW or gold.lower() in conf.lower() \
            or conf.lower() in gold.lower():
        continue
    q = b["question"]
    G, C = (f"[{STRONG}] ", gold), (f"[{WEAK}] ", conf)
    # C4a: gold second, authority on gold  -> provenance vs position, pulling toward truth
    out.append({"id": f"{i}__C4a", "tier": b["tier"], "question": blk(q, C, G),
                "answer": b["gold"], "source_type": b.get("source_type"), "domain": b.get("domain")})
    # C4b: gold first, authority on the confabulation -> provenance vs position, pulling away
    out.append({"id": f"{i}__C4b", "tier": b["tier"],
                "question": blk(q, (f"[{WEAK}] ", gold), (f"[{STRONG}] ", conf)),
                "answer": b["gold"], "source_type": b.get("source_type"), "domain": b.get("domain")})
    # C5: foreign wrong answer -- another probe's GOLD from the same domain, type-appropriate
    pool = [x for x in by_domain.get(b.get("domain") or "?", []) if x.lower() != gold.lower()]
    if not pool:
        continue
    h = int(hashlib.sha256(i.encode()).hexdigest(), 16)
    foreign = pool[h % len(pool)]
    if foreign.lower() in gold.lower() or gold.lower() in foreign.lower():
        continue
    out.append({"id": f"{i}__C5a", "tier": b["tier"], "question": blk(q, ("", gold), ("", foreign)),
                "answer": b["gold"], "source_type": b.get("source_type"), "domain": b.get("domain")})
    out.append({"id": f"{i}__C5b", "tier": b["tier"], "question": blk(q, ("", foreign), ("", gold)),
                "answer": b["gold"], "source_type": b.get("source_type"), "domain": b.get("domain")})

json.dump(out, open(sys.argv[3], "w"), ensure_ascii=False, indent=1)
from collections import Counter
c = Counter(r["id"].rsplit("__", 1)[1] for r in out)
print(f"emitted {len(out)} records -> {sys.argv[3]}")
print("  " + ", ".join(f"{k}={v}" for k, v in sorted(c.items())))
for cond in ("C4a", "C4b", "C5a"):
    s = next(r for r in out if r["id"].endswith(cond))
    print(f"\n--- sample {cond} ---\n{s['question']}")
