#!/usr/bin/env python3
# Flip/hazard lens for the pricing matrix, computed OFFLINE from artifacts we already have:
#   margins: per-token top1-top2 log-prob gap from the f16 base logits file (one-time extract;
#            base format: "_logits_", u32 n_ctx, i32 n_vocab, i32 n_chunk, tokens[n_ctx*n_chunk] i32,
#            then per chunk n_scored x nv u16 where nv = 2*((n_vocab+1)/2)+4; per token the first
#            4 u16 = [scale, min_log_prob] as 2 f32, then q[i]; log_prob_i = scale*q_i + min ->
#            margin = scale*(q(1) - q(2)), monotone in q so top-2 comes from u16 partition).
#   kld dumps: per-cell TURBO_KLD_DUMP (n_chunk x n_pos f32).
# Hazard per token (P1.2 convention): L = KL / (0.5 * margin^2). Statistics per cell vs the
# transition's hi-tier anchor:
#   flip_excess      = frac(L_cell >= 1) - frac(L_anchor >= 1)      (net new flip-hazard tokens)
#   mw_excess_mean   = mean((kld_cell - kld_anchor) / (0.5 m^2))    (margin-weighted paired mean)
#   mw_excess_trim1  = 1%-trimmed version of the same
# plus split-half (even/odd, halves) reliability per (transition, side).
import argparse, os, struct, sys
from collections import defaultdict
import numpy as np

def extract_margins(base_path, out_path):
	f = open(base_path, "rb")
	if f.read(8) != b"_logits_":
		sys.exit("not a logits base file")
	n_ctx, = struct.unpack("<I", f.read(4))
	n_vocab, n_chunk = struct.unpack("<ii", f.read(8))
	n_scored = n_ctx - 1 - n_ctx // 2
	nv = 2 * ((n_vocab + 1) // 2) + 4
	f.seek(8 + 4 + 8 + 4 * n_ctx * n_chunk)
	print(f"base: n_ctx={n_ctx} n_vocab={n_vocab} n_chunk={n_chunk} n_scored={n_scored} nv={nv}")
	margins = np.zeros((n_chunk, n_scored), dtype=np.float32)
	SLICE = 1024
	for c in range(n_chunk):
		done = 0
		while done < n_scored:
			rows = min(SLICE, n_scored - done)
			arr = np.fromfile(f, dtype=np.uint16, count=rows * nv).reshape(rows, nv)
			hdr = arr[:, :4].copy().view(np.float32)  # scale, min_log_prob
			q = arr[:, 4:4 + n_vocab]
			top2 = np.partition(q, n_vocab - 2, axis=1)[:, -2:]
			margins[c, done:done + rows] = hdr[:, 0] * (top2[:, 1].astype(np.float32) - top2[:, 0].astype(np.float32))
			done += rows
		print(f"  chunk {c}: median margin {np.median(margins[c]):.4f} nats, frac<1step {float((margins[c] <= 0).mean()):.4f}")
	margins.tofile(out_path)
	with open(out_path + ".meta", "w") as m:
		m.write(f"{n_chunk} {n_scored}\n")
	return margins

def read_dump(path):
	data = open(path, "rb").read()
	n_pos, n_chunk = struct.unpack_from("<ii", data, 0)
	return np.frombuffer(data, dtype=np.float32, offset=8).reshape(n_chunk, n_pos).astype(np.float64)

def groups(n):
	return {"all": np.arange(n), "even": np.arange(0, n, 2), "odd": np.arange(1, n, 2),
		"firsthalf": np.arange(0, n // 2), "secondhalf": np.arange(n // 2, n)}

def trimmed(x, frac=0.01):
	k = max(1, int(len(x) * frac)); xs = np.sort(x); return float(xs[k:-k].mean())

def spearman(a, b):
	n = len(a)
	if n < 3: return float("nan")
	ra = np.argsort(np.argsort(a)); rb = np.argsort(np.argsort(b))
	return 1 - 6 * float(((ra - rb) ** 2).sum()) / (n * (n * n - 1))

def main():
	ap = argparse.ArgumentParser()
	ap.add_argument("--base", default="/root/night/base27_16k_8ch.kld")
	ap.add_argument("--margins", default="/root/night/margins_q27.f32")
	ap.add_argument("--dumps", default="/root/night/dumps")
	ap.add_argument("--tag", default="q27")
	ap.add_argument("--out", default="/root/night/hazard_q27")
	args = ap.parse_args()

	if os.path.exists(args.margins):
		n_chunk, n_scored = map(int, open(args.margins + ".meta").read().split())
		margins = np.fromfile(args.margins, dtype=np.float32).reshape(n_chunk, n_scored)
	else:
		margins = extract_margins(args.base, args.margins)
	m = margins.astype(np.float64)
	step = np.maximum(m, 1e-6)  # zero-margin = sub-quantization-step tie; keep finite
	denom = 0.5 * step * step

	anchors, cells = {}, defaultdict(list)
	for fn in os.listdir(args.dumps):
		if not fn.startswith(f"pxr_{args.tag}_") or not fn.endswith(".kld"): continue
		name = fn[:-4]; parts = name.split("_")
		if parts[2] == "base": anchors[parts[3]] = name
		else:
			if "-" not in parts[2]:  # addendum cells (tapon/off/alpha ladders) — analyzed separately
				continue
			hi, lo = parts[2].split("-")
			cells[(hi, lo)].append((int(parts[3][1:]), parts[4], name))

	anchor_L = {}
	rows = []
	vals = defaultdict(dict)
	for (hi, lo), lst in sorted(cells.items()):
		if hi not in anchors: continue
		a = read_dump(os.path.join(args.dumps, anchors[hi] + ".kld"))
		if hi not in anchor_L: anchor_L[hi] = (a / denom >= 1.0)
		aL = anchor_L[hi]
		tr = f"{hi}-{lo}"
		for layer, side, name in sorted(lst):
			arr = read_dump(os.path.join(args.dumps, name + ".kld"))
			if arr.shape != a.shape: continue
			L = arr / denom
			mw = (arr - a) / denom
			for gname, gi in groups(arr.shape[0]).items():
				flip_ex = float((L[gi] >= 1.0).mean() - aL[gi].mean())
				st = {"flip_excess": flip_ex,
					"mw_excess_mean": float(mw[gi].mean()),
					"mw_excess_trim1": trimmed(mw[gi].reshape(-1)),
					"mw_excess_median": float(np.median(mw[gi]))}
				rows.append((name, tr, layer, side, gname, st))
				for k, v in st.items(): vals[(tr, side, gname, k)][layer] = v

	keys = ["flip_excess", "mw_excess_mean", "mw_excess_trim1", "mw_excess_median"]
	with open(args.out + "_cells.tsv", "w") as f:
		f.write("name\ttransition\tlayer\tside\tgroup\t" + "\t".join(keys) + "\n")
		for name, tr, layer, side, g, st in rows:
			f.write(f"{name}\t{tr}\t{layer}\t{side}\t{g}\t" + "\t".join(f"{st[k]:.9g}" for k in keys) + "\n")
	with open(args.out + "_reliability.tsv", "w") as f:
		f.write("transition\tside\tstat\trho_even_odd\trho_half\n")
		for (tr, side) in sorted({(t, s) for (t, s, g, k) in vals}):
			for k in keys:
				ve, vo = vals.get((tr, side, "even", k), {}), vals.get((tr, side, "odd", k), {})
				vf, vs = vals.get((tr, side, "firsthalf", k), {}), vals.get((tr, side, "secondhalf", k), {})
				com = sorted(set(ve) & set(vo))
				if len(com) < 3: continue
				r1 = spearman([ve[l] for l in com], [vo[l] for l in com])
				c2 = sorted(set(vf) & set(vs))
				r2 = spearman([vf[l] for l in c2], [vs[l] for l in c2]) if len(c2) >= 3 else float("nan")
				f.write(f"{tr}\t{side}\t{k}\t{r1:.3f}\t{r2:.3f}\n")
	print("margin stats: median", float(np.median(m)), "p10", float(np.percentile(m, 10)), "frac<=0", float((margins <= 0).mean()))
	print("wrote", args.out + "_cells.tsv / _reliability.tsv")

if __name__ == "__main__":
	main()
