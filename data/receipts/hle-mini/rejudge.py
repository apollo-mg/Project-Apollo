#!/usr/bin/env python3
"""Judge saved traces after the fact, so accuracy costs no new generation.

Runs never configured with a judge report a LOWER BOUND: every answer that failed
exact string match is scored wrong. On HLE that is most of them, because gold
answers are terse and models phrase things differently. The traces already hold
the model output and the gold answer, so the judgement can be applied later
against a judge served on any idle box.

JUDGE DESIGN, and why it is not the obvious one:

  A one-token grammar-constrained YES/NO from a reasoning-tuned model is a
  YES-MACHINE. Measured: `Paris` vs `Berlin` -> YES. Forcing an immediate verdict
  from a model trained to think first destroys its judgement entirely, and the
  failure is invisible without a known-negative control -- it looks like a working
  judge that happens to agree a lot.

  So the judge reasons freely and emits `VERDICT: YES|NO` on a final line, which
  is parsed. Validated on six known pairs before use:

    1/2 vs 0.5              YES   correct
    Paris vs Berlin         NO    correct
    sodium ion vs Na+       YES   correct
    42 vs 17                NO    correct
    Frits Zernike vs Zernike NO   STRICT -- arguably should be YES
    yes vs no               NO    correct

  The one disagreement is conservative: this judge is strict about partial names,
  so it biases the score DOWN. A judged number from it is a floor, not a ceiling.

  Judge calls and the judge model are recorded, because a score leaning heavily on
  a local judge measures the judge as much as the subject.
"""
import argparse, glob, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from run_hle_mini import norm, parse_reply, post

VERDICT_PROMPT = (
    "Are these two answers to the same question equivalent?\n\n"
    "Reference answer: {gold}\nSubmitted answer: {ans}\n\n"
    "Think briefly, then end your reply with exactly one line:\n"
    "VERDICT: YES\nor\nVERDICT: NO"
)


def judge(host, gold, ans, timeout=300):
    body = {"messages": [{"role": "user",
                          "content": VERDICT_PROMPT.format(gold=gold, ans=ans)}],
            "temperature": 0, "top_k": 1, "n_predict": 512}
    try:
        d = post(host, body, timeout=timeout)
        m = d["choices"][0]["message"]
        t = (m.get("content") or "") + "\n" + (m.get("reasoning_content") or "")
        v = re.findall(r"VERDICT:\s*(YES|NO)", t, re.I)
        return (v[-1].upper() == "YES") if v else None
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("trace_dir")
    ap.add_argument("--judge-host", default=os.environ.get("JUDGE_HOST", "http://127.0.0.1:8082"))
    a = ap.parse_args()

    files = sorted(glob.glob(os.path.join(a.trace_dir, "*.json")))
    if not files:
        print(f"no traces in {a.trace_dir}"); sys.exit(1)

    n = parsed = exact = judged_yes = unresolved = 0
    rows = []
    for f in files:
        j = json.load(open(f))
        n += 1
        text = (j.get("content") or "") + "\n" + (j.get("reasoning") or "")
        ans, conf = parse_reply(text)
        gold = j.get("gold") or ""
        if not ans:
            rows.append({"id": j.get("id"), "parsed": False, "correct": False})
            continue
        parsed += 1
        if norm(ans) == norm(gold):
            exact += 1
            rows.append({"id": j.get("id"), "parsed": True, "correct": True, "how": "exact"})
            continue
        v = judge(a.judge_host, gold, ans)
        if v is None:
            unresolved += 1
            rows.append({"id": j.get("id"), "parsed": True, "correct": False, "how": "judge_failed"})
        else:
            judged_yes += int(v)
            rows.append({"id": j.get("id"), "parsed": True, "correct": bool(v), "how": "judge"})

    correct = exact + judged_yes
    tag = os.path.basename(a.trace_dir.rstrip("/")).replace("traces_", "")
    print(f"{tag}:  n={n}  parsed={parsed} ({100*parsed/n:.0f}%)  "
          f"exact={exact}  judge_yes={judged_yes}  unresolved={unresolved}")
    print(f"  ACCURACY {100*correct/n:.1f}%  ({correct}/{n})   "
          f"of parsed: {100*correct/parsed:.1f}% ({correct}/{parsed})" if parsed else "")
    out = os.path.join(HERE, f"judged_{tag}.json")
    json.dump({"tag": tag, "n": n, "parsed": parsed, "exact": exact,
               "judge_yes": judged_yes, "unresolved": unresolved,
               "accuracy": round(correct / n, 4) if n else 0,
               "accuracy_of_parsed": round(correct / parsed, 4) if parsed else None,
               "judge_host": a.judge_host, "rows": rows}, open(out, "w"), indent=1)
    print(f"  -> {out}")


if __name__ == "__main__":
    main()
