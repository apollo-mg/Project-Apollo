#!/usr/bin/env python3
"""P-HEAL: is the lost fact GONE, or present-but-outranked?

Decides which mechanism a post-REAP healing pass would have to be:
  gold still high-probability  -> re-sharpening (cheap, LoRA-scale) -- h4rm0n1c's analogy holds
  gold far down the tail       -> re-learning (training cost, facts must be in the healing corpus)

TWO MEASURES, BOTH REPORTED.

  (A) POSITION-0 RANK -- what PREREG_.../ERROR_STRUCTURE_AND_HEALING.md registered as P-HEAL1/2.
      A capability probe run before this harness existed showed it is STYLE-CONFOUNDED on this
      model: for "What is the capital of Canada?" the pruned arm's top-3 at position 0 is
      'The' (-0.82), 'O' (-1.50, Ottawa), 'Toronto' (-1.70). Gold OUTRANKS the wrong answer the
      model actually emitted -- because position 0 selects a FRAMING ("The capital of ... is"),
      not a fact. Scored anyway, exactly as registered; see the receipt for why it is not the
      measure to interpret.

  (B) ANSWER-SLOT RANK -- the discriminating one. Truncate the pruned model's OWN response
      immediately before its answer span and read gold vs emitted AT THAT POSITION. That is where
      the fact is actually committed. Only run on cases with an UNAMBIGUOUS truncation point;
      the count of cases that admit one is reported, never papered over with a heuristic.

TOKENIZATION. 'Ottawa' is ['O','tt','awa'] but 'Toronto' is ['Toronto']. Summed logprobs across
different token counts are not commensurable, so the comparison statistic is PER-TOKEN MEAN
logprob over the full forced span, with token counts reported alongside.

CENSORING. n_probs caps at TOP_N; a forced token outside it has no exact logprob. Those are
recorded rank=None with logprob_floor = the TOP_N-th entry's logprob (an UPPER bound on the true
value). Never silently imputed.

CANARY. cache_prompt makes this cheap but means a mid-run server restart would change numbers
invisibly. A fixed probe's top-1 logprob is recorded at start and end; if it moves, the run is void.
"""
import argparse, json, os, sys, time, urllib.request

SYSTEM_MSG = "Answer factual questions directly and concisely. If you don't know, say 'I don't know'."
TOP_N = 100
CANARY_Q = "What is the capital of France?"


def post(base, path, d, t=180):
    r = urllib.request.Request(base + path, data=json.dumps(d).encode(),
                               headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(r, timeout=t).read().decode())


def tmpl(base, q):
    return post(base, "/apply-template", {
        "messages": [{"role": "system", "content": SYSTEM_MSG}, {"role": "user", "content": q}],
        "chat_template_kwargs": {"enable_thinking": False}})["prompt"]


def toks(base, s):
    return [t["piece"] for t in post(base, "/tokenize", {"content": s, "with_pieces": True})["tokens"]]


def dist(base, prompt):
    """top-TOP_N (token, logprob) at the next position after `prompt`."""
    d = post(base, "/completion", {"prompt": prompt, "n_predict": 1, "n_probs": TOP_N,
                                   "temperature": 0, "cache_prompt": True})
    slot = d["completion_probabilities"][0]
    ent = slot.get("top_logprobs") or slot.get("probs") or []
    return [(e.get("token"), e.get("logprob")) for e in ent]


def score_span(base, prefix, span):
    """Teacher-force `span` after `prefix`. -> per-token records + summary.

    One request per token; the shared prefix is server-cached so this is cheap.
    """
    pieces = toks(base, span)
    recs, prompt = [], prefix
    for pc in pieces:
        top = dist(base, prompt)
        rank, lp = None, None
        for i, (tk, l) in enumerate(top):
            if tk == pc:
                rank, lp = i + 1, l
                break
        recs.append({"piece": pc, "rank": rank, "logprob": lp,
                     "floor": top[-1][1] if rank is None and top else None})
        prompt += pc
    known = [r["logprob"] for r in recs if r["logprob"] is not None]
    cens = sum(1 for r in recs if r["rank"] is None)
    return {"span": span, "n_tok": len(pieces), "censored": cens,
            "mean_logprob": (sum(known) / len(known)) if known and not cens else None,
            "first_rank": recs[0]["rank"] if recs else None, "tokens": recs}


def find_slot(response, gold_variants, emitted_answer):
    """Prefix of `response` ending immediately before its answer span, or None if ambiguous.

    Deliberately conservative: the answer must appear exactly once, and not at position 0 (which
    would make the slot empty and collapse measure B into measure A).
    """
    if not emitted_answer:
        return None
    i = response.find(emitted_answer)
    if i <= 0:
        return None
    if response.count(emitted_answer) != 1:
        return None
    return response[:i]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--endpoint", default="http://127.0.0.1:8092")
    ap.add_argument("--cases", required=True, help="JSON produced by build_heal_cases.py")
    ap.add_argument("--out", required=True)
    ap.add_argument("--arm", required=True, choices=["wrong", "refusal"])
    a = ap.parse_args()

    cases = [c for c in json.load(open(a.cases)) if c["arm"] == a.arm]
    done = set()
    if os.path.exists(a.out):
        for l in open(a.out):
            try:
                done.add(json.loads(l)["id"])
            except Exception:
                pass
    todo = [c for c in cases if c["id"] not in done]
    print(f"[heal] arm={a.arm}: {len(cases)} cases, {len(done)} done, {len(todo)} to run", flush=True)
    if not todo:
        return

    can0 = dist(a.endpoint, tmpl(a.endpoint, CANARY_Q))[0]
    print(f"[heal] canary start: {can0!r}", flush=True)
    with urllib.request.urlopen(a.endpoint + "/props", timeout=30) as r:   # GET, not POST
        mp = json.loads(r.read().decode()).get("model_path")
    print(f"[heal] model: {mp}", flush=True)

    out = open(a.out, "a")
    t0 = time.time()
    for n, c in enumerate(todo, 1):
        prefix = tmpl(a.endpoint, c["question"])
        rec = {"id": c["id"], "arm": a.arm, "tier": c["tier"], "question": c["question"],
               "gold": c["gold"], "emitted": c["emitted"], "emitted_answer": c.get("emitted_answer")}
        # (A) position 0 -- as registered
        rec["A_gold"] = score_span(a.endpoint, prefix, c["gold"])
        rec["A_emitted"] = score_span(a.endpoint, prefix, c["emitted"][:80])
        # (B) answer slot -- the interpretable one
        slot = find_slot(c["emitted"], c["gold"], c.get("emitted_answer"))
        rec["slot_found"] = slot is not None
        if slot is not None:
            rec["slot_prefix"] = slot
            rec["B_gold"] = score_span(a.endpoint, prefix + slot, c["gold"])
            rec["B_emitted"] = score_span(a.endpoint, prefix + slot, c["emitted_answer"])
        out.write(json.dumps(rec, ensure_ascii=False) + "\n")
        out.flush()
        if n % 10 == 0 or n == len(todo):
            el = time.time() - t0
            print(f"  [{n}/{len(todo)}] {el:.0f}s, eta {(len(todo)-n)/max(n/el,1e-9):.0f}s", flush=True)
    out.close()

    can1 = dist(a.endpoint, tmpl(a.endpoint, CANARY_Q))[0]
    print(f"[heal] canary end:   {can1!r}", flush=True)
    # Tolerance is MEASURED, not guessed. 12 consecutive reads inside one process are bit-identical
    # (spread 0.00000); across invocations the value drifts ~0.03 nats with the server's KV-cache
    # state. So require the same top-1 token and a drift far below anything a model swap could
    # produce. Exact equality would void every run on this endpoint for no reason.
    CAN_TOL = 0.5
    if can0[0] != can1[0] or abs(can0[1] - can1[1]) > CAN_TOL:
        print(f"[heal] *** CANARY MOVED ({can0} -> {can1}) — server changed mid-run. VOID. ***",
              flush=True)
        sys.exit(1)
    print(f"[heal] done in {time.time()-t0:.0f}s, canary stable "
          f"(drift {abs(can0[1]-can1[1]):.4f} nats, tol {CAN_TOL})", flush=True)


if __name__ == "__main__":
    main()
