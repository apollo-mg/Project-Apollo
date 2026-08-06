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


def grade(gold, response, long_answer_words=25):
    """-> (verdict, reason). verdict in CORRECT / WRONG / REFUSAL / AMBIGUOUS."""
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
                v, why = grade(rec["gold"], rec.get("response", ""), args.long_answer_words)
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
    hdr = f"{'arm':<14}{'tier':<6}{'n':>5}{'corr':>6}{'wrong':>6}{'refus':>6}{'ambig':>6}{'raw':>9}{'penalized':>11}"
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
            for k, v in (("n", n), ("CORRECT", c), ("WRONG", w), ("REFUSAL", rf), ("AMBIGUOUS", am)):
                tot[k] += v
            raw, pen = c / n, (c + HALLUCINATION_PENALTY * w) / n
            print(f"{lab:<14}{t:<6}{n:>5}{c:>6}{w:>6}{rf:>6}{am:>6}{raw:>8.1%}{pen:>11.3f}")
            rows.append(dict(arm=lab, tier=t, n=n, correct=c, wrong=w, refusal=rf,
                             ambiguous=am, raw=round(raw, 4), penalized=round(pen, 4)))
        n = tot["n"]
        if n:
            raw = tot["CORRECT"] / n
            pen = (tot["CORRECT"] + HALLUCINATION_PENALTY * tot["WRONG"]) / n
            print(f"{lab:<14}{'ALL':<6}{n:>5}{tot['CORRECT']:>6}{tot['WRONG']:>6}"
                  f"{tot['REFUSAL']:>6}{tot['AMBIGUOUS']:>6}{raw:>8.1%}{pen:>11.3f}")
            rows.append(dict(arm=lab, tier="ALL", n=n, correct=tot["CORRECT"], wrong=tot["WRONG"],
                             refusal=tot["REFUSAL"], ambiguous=tot["AMBIGUOUS"],
                             raw=round(raw, 4), penalized=round(pen, 4)))
            print("-" * len(hdr))

    if args.csv and rows:
        with open(args.csv, "w", newline="") as f:
            wr = csv.DictWriter(f, fieldnames=list(rows[0]))
            wr.writeheader()
            wr.writerows(rows)
        print(f"[ikp] summary -> {args.csv}", file=sys.stderr)


if __name__ == "__main__":
    main()
