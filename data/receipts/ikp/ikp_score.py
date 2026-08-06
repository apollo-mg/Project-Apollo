#!/usr/bin/env python3
"""Score IKP runs produced by ikp_run.py. Deterministic by default; judge-ready by design.

WHY DETERMINISTIC RATHER THAN AN LLM JUDGE.
Li's ikp_estimate.py grades with gemini-3-flash via OpenRouter. For his purpose (absolute accuracy
of one model, extrapolated to a parameter count) a judge is the right call -- it handles paraphrase
and aliasing. For OUR purpose it is the wrong call: we are comparing 6-7 arms of the SAME model
against each other, and a stochastic judge injects variance that is not in the thing being measured.
A fixed rule applied identically to every arm cannot favour one arm over another.

The cost is that our absolute numbers will NOT equal Li's or quesma's. That is acceptable and worth
stating plainly: our claim is about the *ordering and spacing* of arms on one ladder, not about
reproducing anyone's headline accuracy.

Anything the deterministic rule cannot settle is emitted to --judge-queue rather than guessed, so a
judge pass can adjudicate only the genuinely ambiguous minority. Raw responses are never discarded.

Two accuracies are reported, following Li:
  raw        = correct / total
  penalized  = (correct + HALLUCINATION_PENALTY * wrong) / total     [HALLUCINATION_PENALTY = -1.0]
Refusals score 0 in both -- saying "I don't know" is not punished, confidently inventing is.
This matters here: quantization damage can show up as *more hallucination* rather than fewer
correct answers, and raw accuracy alone would hide that.

Usage:
  ./ikp_score.py ikp_bf16.jsonl ikp_tq4_1s.jsonl ...
  ./ikp_score.py ikp_*.jsonl --judge-queue ambiguous.jsonl --csv summary.csv
"""
import argparse, csv, json, re, sys, unicodedata
from collections import defaultdict

HALLUCINATION_PENALTY = -1.0

REFUSAL_PAT = re.compile(
    r"\b(i (do not|don't) know|do not know|don'?t know|not sure|unsure|not certain|"
    r"cannot determine|can'?t determine|no idea|unable to (answer|determine|say)|"
    r"insufficient information|cannot answer|can'?t answer)\b", re.I)

ARTICLES = re.compile(r"^(the|a|an)\s+", re.I)


def norm(s):
    """Casefold, strip accents and punctuation, collapse whitespace, drop a leading article."""
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.casefold()
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return ARTICLES.sub("", s).strip()


def grade(gold, response, long_answer_words=25, finish_reason=None):
    """-> (verdict, reason). verdict in CORRECT / WRONG / REFUSAL / AMBIGUOUS / NO_ANSWER.

    NO_ANSWER is checked FIRST and deliberately. A generation that hit max_tokens produces an empty
    or partial string, which the empty-response rule below would book as a REFUSAL and the substring
    rule would book as WRONG. Both are the wrong attribution: the probe was never answered. On a
    reasoning model an unterminated <think> chain does this to every probe at once, and if one arm
    of a comparison thinks slightly longer than the other you get a clean, entirely spurious
    knowledge cliff -- which is what the Puzzle-75B HumanEval+ gap turned out to be.
    """
    if finish_reason == "length":
        return "NO_ANSWER", "hit max_tokens"
    if not response or not response.strip():
        return "REFUSAL", "empty"
    if REFUSAL_PAT.search(response):
        return "REFUSAL", "refusal phrase"

    r = norm(response)
    alts = [norm(a) for a in str(gold).split(";") if a.strip()]
    if not alts:
        return "AMBIGUOUS", "no gold"

    hit = any(a and re.search(rf"(?<!\w){re.escape(a)}(?!\w)", r) for a in alts)
    n_words = len(response.split())

    if hit:
        # Li's rule 4: a scattergun of guesses that happens to contain the gold is not a correct
        # answer. Substring matching cannot distinguish that from a correct answer with context,
        # so hand long responses to a judge instead of scoring them either way.
        if n_words > long_answer_words:
            return "AMBIGUOUS", f"gold present but response is {n_words} words"
        return "CORRECT", "exact/alias match"
    if n_words > long_answer_words:
        return "AMBIGUOUS", f"no match and response is {n_words} words"
    return "WRONG", "no match"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--judge-queue", help="write AMBIGUOUS records here for an adjudication pass")
    ap.add_argument("--csv", help="write the per-arm summary as CSV")
    ap.add_argument("--long-answer-words", type=int, default=25)
    args = ap.parse_args()

    stats = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))  # label -> tier -> verdict
    ambiguous = []
    for path in args.files:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                v, why = grade(rec["gold"], rec.get("response", ""), args.long_answer_words,
                               rec.get("finish_reason"))
                stats[rec["label"]][rec["tier"]][v] += 1
                if v == "AMBIGUOUS":
                    ambiguous.append({**rec, "reason": why})

    if args.judge_queue and ambiguous:
        with open(args.judge_queue, "w") as f:
            for r in ambiguous:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"[ikp] {len(ambiguous)} ambiguous -> {args.judge_queue}", file=sys.stderr)

    rows = []
    tiers = sorted({t for lab in stats for t in stats[lab]})
    na_rate = {}          # label -> overall no_answer fraction, for the divergence check below
    hdr = (f"{'arm':<14}{'tier':<6}{'n':>5}{'corr':>6}{'wrong':>6}{'refus':>6}{'ambig':>6}"
           f"{'noans':>7}{'raw':>9}{'answered':>10}{'penalized':>11}")
    print(hdr)
    print("-" * len(hdr))
    for lab in sorted(stats):
        tot = defaultdict(int)
        for t in tiers:
            d = stats[lab].get(t)
            if not d:
                continue
            n = sum(d.values())
            c, w, rf, am = d["CORRECT"], d["WRONG"], d["REFUSAL"], d["AMBIGUOUS"]
            na = d["NO_ANSWER"]
            for k, v in (("n", n), ("CORRECT", c), ("WRONG", w), ("REFUSAL", rf),
                         ("AMBIGUOUS", am), ("NO_ANSWER", na)):
                tot[k] += v
            # raw is over ALL probes (comparable with earlier receipts); answered excludes NO_ANSWER
            # so a token-budget artefact cannot masquerade as a recall deficit.
            raw = c / n
            ans_n = n - na
            ans = c / ans_n if ans_n else float("nan")
            pen = (c + HALLUCINATION_PENALTY * w) / n
            print(f"{lab:<14}{t:<6}{n:>5}{c:>6}{w:>6}{rf:>6}{am:>6}{na:>7}"
                  f"{raw:>8.1%}{ans:>9.1%}{pen:>11.3f}")
            rows.append(dict(arm=lab, tier=t, n=n, correct=c, wrong=w, refusal=rf,
                             ambiguous=am, no_answer=na, n_answered=ans_n,
                             raw=round(raw, 4), answered=round(ans, 4) if ans_n else None,
                             penalized=round(pen, 4)))
        n = tot["n"]
        if n:
            c, w, na = tot["CORRECT"], tot["WRONG"], tot["NO_ANSWER"]
            ans_n = n - na
            raw = c / n
            ans = c / ans_n if ans_n else float("nan")
            pen = (c + HALLUCINATION_PENALTY * w) / n
            na_rate[lab] = na / n
            print(f"{lab:<14}{'ALL':<6}{n:>5}{c:>6}{w:>6}{tot['REFUSAL']:>6}{tot['AMBIGUOUS']:>6}"
                  f"{na:>7}{raw:>8.1%}{ans:>9.1%}{pen:>11.3f}")
            rows.append(dict(arm=lab, tier="ALL", n=n, correct=c, wrong=w,
                             refusal=tot["REFUSAL"], ambiguous=tot["AMBIGUOUS"], no_answer=na,
                             n_answered=ans_n, raw=round(raw, 4),
                             answered=round(ans, 4) if ans_n else None, penalized=round(pen, 4)))
            print("-" * len(hdr))

    # G-5: divergent termination behaviour invalidates the accuracy delta between arms.
    if len(na_rate) > 1:
        lo, hi = min(na_rate.values()), max(na_rate.values())
        print(f"\n[G-5] no_answer rate: " +
              ", ".join(f"{k}={v:.1%}" for k, v in sorted(na_rate.items())))
        if hi - lo > 0.02:
            print(f"[G-5] *** SPREAD {hi-lo:.1%} EXCEEDS 2pp -- the accuracy delta between these "
                  f"arms is NOT interpretable as a knowledge difference. The arms terminated "
                  f"differently. Explain that first; it may be the more interesting finding. ***",
                  file=sys.stderr)
        else:
            print(f"[G-5] spread {hi-lo:.1%} within 2pp -- arms terminated comparably.")

    if args.csv and rows:
        with open(args.csv, "w", newline="") as f:
            wr = csv.DictWriter(f, fieldnames=list(rows[0]))
            wr.writeheader()
            wr.writerows(rows)
        print(f"[ikp] summary -> {args.csv}", file=sys.stderr)


if __name__ == "__main__":
    main()
