#!/usr/bin/env python3
"""Run the fixed HLE subset against any OpenAI-compatible endpoint.

Grading is deterministic wherever it can be, and only falls back to a judge when
it must:

  multipleChoice (41/200)  -- parsed and compared directly. No judge, ever.
  exactMatch     (159/200) -- normalised string compare first. A judge is only
                              consulted when normalisation says "different", to
                              catch equivalent phrasings (1/2 vs 0.5, "Na+" vs
                              "sodium ion"). Judge calls are counted and reported,
                              because a score that leans heavily on a local judge
                              is a measurement of the judge as much as the model.

With no judge configured the runner still completes and reports a hard lower
bound (unmatched = wrong) plus the number of items a judge would have been asked
about. That number is the thing to look at before trusting any judged score.

Confidence is elicited in HLE's own output format so RMS calibration error is
available. On this fleet calibration is arguably the more interesting metric:
`battle16gb` Finding 5 found a 25 pp gap that turned out to be a stopping-rule
failure rather than an answering failure, and an overconfident-when-wrong model
is the same class of defect showing up in a different place.

CONTENT HYGIENE: results files carry ids, correctness, confidence, and token
counts -- never question text, never answer text, never model output. Full traces
go to traces_<tag>/ which is gitignored. HLE ships a canary asking to stay out of
training corpora; published receipts are exactly the wrong place for it.
"""
import argparse, json, os, re, statistics, sys, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))

# HLE's own response format, so the confidence field is available for calibration.
PROMPT_TMPL = """{question}

Your response should be in the following format:
Explanation: {{your explanation for your final answer}}
Exact Answer: {{your succinct, final answer}}
Confidence: {{your confidence score between 0% and 100% for your answer}}"""


def post(host, body, timeout=1800):
    req = urllib.request.Request(f"{host}/v1/chat/completions",
                                 data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def norm(s):
    """Aggressive but symmetric normalisation, applied to both sides."""
    s = (s or "").strip().lower()
    s = re.sub(r"\\\\[a-z]+\{([^}]*)\}", r"\1", s)     # strip simple latex wrappers
    s = s.replace("$", "").replace("\\", "").replace(",", "")
    s = re.sub(r"[\s_]+", " ", s)
    s = re.sub(r"[.​]+$", "", s)
    return s.strip()


def parse_reply(text):
    ans = re.search(r"Exact Answer\s*:\s*(.+?)(?:\n|$)", text, re.I | re.S)
    conf = re.search(r"Confidence\s*:\s*(\d+(?:\.\d+)?)\s*%?", text, re.I)
    return (ans.group(1).strip() if ans else ""),  (float(conf.group(1)) if conf else None)


def judge_equivalent(host, model_ans, gold, question_hint=""):
    """Ask a local judge whether two short answers are equivalent. Yes/no only."""
    body = {"messages": [{"role": "user", "content":
             "You are grading a short answer. Reply with exactly one word: YES if "
             "the two answers are mathematically or semantically equivalent, NO if "
             "they are not. Do not explain.\n\n"
             f"Reference answer: {gold}\nSubmitted answer: {model_ans}"}],
            "temperature": 0, "top_k": 1, "n_predict": 8}
    try:
        d = post(host, body, timeout=300)
        out = (d["choices"][0]["message"].get("content") or "").strip().upper()
        return out.startswith("YES")
    except Exception:
        return None


def rms_calibration_error(rows, bins=10):
    """HLE reports RMS calibration error alongside accuracy."""
    have = [r for r in rows if r.get("confidence") is not None]
    if not have:
        return None
    tot, n = 0.0, 0
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        grp = [r for r in have if lo < (r["confidence"] / 100.0) <= hi or (b == 0 and r["confidence"] == 0)]
        if not grp:
            continue
        acc = sum(1 for r in grp if r["correct"]) / len(grp)
        conf = statistics.mean(r["confidence"] / 100.0 for r in grp)
        tot += len(grp) * (acc - conf) ** 2
        n += len(grp)
    return (tot / n) ** 0.5 if n else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tag")
    ap.add_argument("--host", default=os.environ.get("HOST", "http://127.0.0.1:8082"))
    ap.add_argument("--judge-host", default=os.environ.get("JUDGE_HOST"))
    ap.add_argument("--manifest", default=os.path.join(HERE, "subset_v1.json"))
    ap.add_argument("--limit", type=int, help="pilot mode: first N questions only")
    ap.add_argument("--max-tokens", type=int, default=8192,
                    help="HLE recommends >=8192; below this, truncation is the result")
    a = ap.parse_args()

    man = json.load(open(a.manifest))
    ids = man["ids"][:a.limit] if a.limit else man["ids"]
    print(f"subset {man['name']}  n={len(ids)}  id_sha256={man['id_set_sha256'][:16]}")

    from datasets import load_dataset
    ds = load_dataset("cais/hle", split="test")
    by_id = {}
    for i in range(len(ds)):
        if ds[i]["id"] in set(ids):
            by_id[ds[i]["id"]] = ds[i]

    tdir = os.path.join(HERE, f"traces_{a.tag}")
    os.makedirs(tdir, exist_ok=True)
    rows, judged, t_start = [], 0, time.time()

    for k, qid in enumerate(ids, 1):
        q = by_id.get(qid)
        if q is None:
            print(f"  [{k}/{len(ids)}] {qid} MISSING from dataset"); continue
        body = {"messages": [{"role": "user",
                              "content": PROMPT_TMPL.format(question=q["question"])}],
                "temperature": 0, "top_k": 1, "seed": 1234,
                "n_predict": a.max_tokens, "timings_per_token": True}
        t0 = time.time()
        try:
            d = post(a.host, body)
        except Exception as e:
            rows.append({"id": qid, "category": q["category"], "error": f"{type(e).__name__}"})
            print(f"  [{k}/{len(ids)}] {q['category'][:18]:18s} ERROR {type(e).__name__}", flush=True)
            continue
        dt = time.time() - t0
        ch = d["choices"][0]
        msg = ch.get("message", {})
        text = msg.get("content") or ""
        reasoning = msg.get("reasoning_content") or ""
        finish = ch.get("finish_reason")
        toks = (d.get("usage") or {}).get("completion_tokens")
        model_ans, conf = parse_reply(text)
        gold = q["answer"]

        if q["answer_type"] == "multipleChoice":
            correct = norm(model_ans) == norm(gold) or norm(model_ans).startswith(norm(gold))
            how = "mc"
        else:
            correct = norm(model_ans) == norm(gold)
            how = "exact"
            if not correct and a.judge_host:
                v = judge_equivalent(a.judge_host, model_ans, gold)
                judged += 1
                if v is not None:
                    correct, how = v, "judge"
            elif not correct:
                how = "needs_judge"

        rows.append({"id": qid, "category": q["category"], "answer_type": q["answer_type"],
                     "correct": bool(correct), "graded_by": how, "confidence": conf,
                     "finish_reason": finish, "completion_tokens": toks,
                     "reasoning_chars": len(reasoning), "answer_parsed": bool(model_ans),
                     "wall_s": round(dt, 1)})
        # full trace, gitignored -- keeps model output out of the repo
        json.dump({"id": qid, "prompt_tokens": (d.get("usage") or {}).get("prompt_tokens"),
                   "content": text, "reasoning": reasoning, "gold": gold,
                   "finish_reason": finish},
                  open(os.path.join(tdir, f"{qid}.json"), "w"), indent=1)
        acc = sum(1 for r in rows if r.get("correct")) / len(rows)
        print(f"  [{k}/{len(ids)}] {q['category'][:18]:18s} "
              f"{'OK ' if correct else '.  '} {how:11s} conf={str(conf):>5} "
              f"tok={toks} fin={finish} run_acc={acc:.3f}", flush=True)

    ok = [r for r in rows if "error" not in r]
    n_ok = len(ok)
    acc = sum(1 for r in ok if r["correct"]) / n_ok if n_ok else 0
    trunc = sum(1 for r in ok if r["finish_reason"] == "length")
    noans = sum(1 for r in ok if not r["answer_parsed"])
    ce = rms_calibration_error(ok)
    out = {"tag": a.tag, "subset": man["name"], "id_set_sha256": man["id_set_sha256"],
           "n": n_ok, "accuracy": round(acc, 4),
           "rms_calibration_error": round(ce, 4) if ce is not None else None,
           "truncated": trunc, "no_answer_parsed": noans,
           "judge_calls": judged, "judge_host_set": bool(a.judge_host),
           "unresolved_needs_judge": sum(1 for r in ok if r["graded_by"] == "needs_judge"),
           "wall_hours": round((time.time() - t_start) / 3600, 2),
           "by_category": {}, "rows": rows}
    for c in sorted({r["category"] for r in ok}):
        g = [r for r in ok if r["category"] == c]
        out["by_category"][c] = {"n": len(g),
                                 "acc": round(sum(1 for r in g if r["correct"]) / len(g), 4)}
    p = os.path.join(HERE, f"results_{a.tag}.json")
    json.dump(out, open(p, "w"), indent=1)

    print(f"\n=== {a.tag} ===")
    print(f"  accuracy            {acc*100:.1f}%   ({sum(1 for r in ok if r['correct'])}/{n_ok})")
    print(f"  RMS calibration err {ce if ce is None else round(ce,4)}")
    print(f"  truncated (length)  {trunc}     no answer parsed {noans}")
    if out["unresolved_needs_judge"]:
        print(f"  !! {out['unresolved_needs_judge']} items unresolved with no judge configured — "
              f"this accuracy is a LOWER BOUND")
    else:
        print(f"  judge calls         {judged}")
    for c, v in out["by_category"].items():
        print(f"    {c:44s} {v['acc']*100:5.1f}%  (n={v['n']})")
    print(f"-> {p}")


if __name__ == "__main__":
    main()
