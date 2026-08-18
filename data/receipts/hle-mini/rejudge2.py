#!/usr/bin/env python3
"""Re-grade saved HLE traces with the B2 parse fix and a structural outcome breakdown.

WHAT CHANGED FROM rejudge.py
  1. B2 FIX. rejudge.py parsed `content + reasoning` unconditionally. RESULT_B2_PARSE_RATE
     showed every parse that gains produces is a TRUNCATED response (7/7, finish=length),
     43% of which contain MULTIPLE "Exact Answer:" strings -- drafts, not conclusions. A
     truncated generation by construction never emitted a final answer. So reasoning is
     parsed ONLY when the response actually finished.
  2. OUTCOME CLASSES instead of a single accuracy. The question "was the model right, wrong,
     close, or was the harness broken?" cannot be answered by one number, and the four cases
     have completely different fixes.

OUTCOME CLASSES
  right_exact       parsed, normalises equal to gold
  right_judge       parsed, judge says equivalent
  wrong             parsed, judge says not equivalent
  judge_failed      parsed, judge call errored -- unresolved, NOT counted as wrong
  no_answer_trunc   finish=length, nothing parseable   -> BUDGET failure
  no_answer_stop    finish=stop,   nothing parseable   -> FORMAT/HARNESS failure
The last two are the ones people conflate. Truncation is a budget problem; a finished
response with no parseable answer is a prompt/format problem. They need opposite fixes.

The judge itself is UNCHANGED from rejudge.py -- same VERDICT: YES|NO prompt, validated
there on six known pairs and documented as strict (biases the score DOWN, so a judged
number is a floor). Do not "improve" it without re-running that validation.

Aggregate counts only. No question text, answer text, or per-question outcomes are printed
or written, per the HLE content-hygiene rule.
"""
import argparse, glob, json, os, sys, difflib
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from run_hle_mini import norm, parse_reply
from rejudge import judge

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("trace_dirs", nargs="+")
    ap.add_argument("--judge-host", default=os.environ.get("JUDGE_HOST", "http://127.0.0.1:8082"))
    ap.add_argument("--judge-model", default=os.environ.get("JUDGE_MODEL", "unrecorded"))
    ap.add_argument("--dry-run", action="store_true", help="classify only, no judge calls")
    a = ap.parse_args()

    grand = {}
    for td in a.trace_dirs:
        files = sorted(glob.glob(os.path.join(td, "*.json")))
        if not files: continue
        c = dict(right_exact=0, right_judge=0, wrong=0, judge_failed=0,
                 no_answer_trunc=0, no_answer_stop=0)
        near = []                      # similarity of judge-NO answers: is "almost" real?
        for f in files:
            j = json.load(open(f))
            content = j.get("content") or ""
            reasoning = j.get("reasoning") or ""
            finished = (j.get("finish_reason") or "") != "length"
            # B2 fix: reasoning is only admissible when the response actually finished
            text = content + ("\n" + reasoning if finished else "")
            ans, _ = parse_reply(text)
            gold = j.get("gold") or ""
            if not ans:
                c["no_answer_trunc" if not finished else "no_answer_stop"] += 1
                continue
            if norm(ans) == norm(gold):
                c["right_exact"] += 1; continue
            if a.dry_run:
                c["wrong"] += 1
                near.append(difflib.SequenceMatcher(None, norm(ans), norm(gold)).ratio())
                continue
            v = judge(a.judge_host, gold, ans)
            if v is None: c["judge_failed"] += 1
            elif v:       c["right_judge"] += 1
            else:
                c["wrong"] += 1
                near.append(difflib.SequenceMatcher(None, norm(ans), norm(gold)).ratio())
        n = sum(c.values())
        right = c["right_exact"] + c["right_judge"]
        tag = os.path.basename(td.rstrip("/")).replace("traces_", "")
        grand[tag] = dict(n=n, right=right, **c,
                          near_max=round(max(near), 3) if near else None)
        print(f"{tag:<20} n={n:<3} right={right}  wrong={c['wrong']}  "
              f"no_ans(trunc)={c['no_answer_trunc']}  no_ans(stop)={c['no_answer_stop']}  "
              f"judge_failed={c['judge_failed']}")
    tot = {k: sum(v[k] for v in grand.values()) for k in
           ("n","right","right_exact","right_judge","wrong","judge_failed",
            "no_answer_trunc","no_answer_stop")}
    print("-"*96)
    print(f"{'TOTAL':<20} n={tot['n']:<3} right={tot['right']} "
          f"(exact {tot['right_exact']} / judge {tot['right_judge']})  wrong={tot['wrong']}  "
          f"no_ans(trunc)={tot['no_answer_trunc']}  no_ans(stop)={tot['no_answer_stop']}  "
          f"judge_failed={tot['judge_failed']}")
    gradeable = tot["right"] + tot["wrong"]
    if gradeable:
        print(f"\naccuracy over GRADEABLE responses : {100*tot['right']/gradeable:.1f}% "
              f"({tot['right']}/{gradeable})")
    if tot["n"]:
        print(f"accuracy over ALL attempts        : {100*tot['right']/tot['n']:.1f}% "
              f"({tot['right']}/{tot['n']})")
        print(f"budget failures (truncated)       : {100*tot['no_answer_trunc']/tot['n']:.0f}%")
        print(f"format failures (finished, no ans): {tot['no_answer_stop']}")
    out = os.path.join(HERE, "judged_v2_summary.json")
    json.dump(dict(judge_host=a.judge_host, judge_model=a.judge_model,
                   dry_run=a.dry_run, per_run=grand, total=tot), open(out,"w"), indent=1)
    print(f"\n-> {out}")

if __name__ == "__main__":
    main()
