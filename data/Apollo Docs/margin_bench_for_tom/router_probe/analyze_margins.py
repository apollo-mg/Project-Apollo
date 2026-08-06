#!/usr/bin/env python3
# Aggregate answer-token logprob margins from probe_router.py results (lp field).
# Margin = chosen-token logprob minus runner-up logprob; computed over the tokens
# spanning the expected FINAL_TARGET string in the output.
import argparse, json, math, sys

def target_span_margins(rec):
	lp = rec.get("lp") or []
	if not lp:
		return None
	toks = [t[0] for t in lp]
	text = "".join(toks)
	tgt = rec["expected_target"]
	pos = text.find(tgt)
	if pos < 0:
		return None
	margins, logprobs = [], []
	off = 0
	for tok, l, ru in lp:
		start, end = off, off + len(tok)
		off = end
		if end <= pos or start >= pos + len(tgt):
			continue
		logprobs.append(l)
		if ru is not None:
			margins.append(l - ru)
	if not margins:
		return None
	return margins, logprobs

def main():
	ap = argparse.ArgumentParser()
	ap.add_argument("results", nargs="+")
	args = ap.parse_args()

	print(f"{'label':22s} {'n':>4s} {'mean_margin':>11s} {'min_margin':>10s} {'p10_margin':>10s} "
		f"{'mean_lp':>8s} {'frac_m<5':>8s}")
	for path in args.results:
		label = path
		case_min, case_mean, case_lp = [], [], []
		n_low = n_tok = 0
		for line in open(path, encoding="utf-8"):
			if not line.strip():
				continue
			rec = json.loads(line)
			label = rec.get("label") or label
			r = target_span_margins(rec)
			if r is None:
				continue
			margins, logprobs = r
			case_min.append(min(margins))
			case_mean.append(sum(margins) / len(margins))
			case_lp.append(sum(logprobs) / len(logprobs))
			n_low += sum(1 for m in margins if m < 5.0)
			n_tok += len(margins)
		if not case_min:
			print(f"{path}: no scorable cases", file=sys.stderr)
			continue
		n = len(case_min)
		srt = sorted(case_min)
		p10 = srt[max(0, int(0.10 * n) - 1)] if n >= 10 else srt[0]
		print(f"{label:22s} {n:4d} {sum(case_mean)/n:11.3f} {sum(case_min)/n:10.3f} {p10:10.3f} "
			f"{sum(case_lp)/n:8.4f} {n_low/max(1,n_tok):8.4f}")

if __name__ == "__main__":
	main()
