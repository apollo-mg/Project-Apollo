import json, sys, itertools
import numpy as np

# Paired per-case min-margin comparison across probe cells.
# margin per token = lp(chosen) - lp(runner-up); per case = min over tokens.

def load(path):
	d = {}
	for line in open(path):
		r = json.loads(line)
		margins = [t[1] - t[2] for t in r.get("lp", []) if len(t) >= 3 and t[2] is not None]
		if margins:
			d[r["id"]] = min(margins)
	return d

def main(paths):
	cells = {}
	for p in paths:
		name = p.split("lp_")[-1].replace(".jsonl", "")
		cells[name] = load(p)
	names = list(cells)
	ids = sorted(set.intersection(*[set(cells[n]) for n in names]))
	print(f"common cases: {len(ids)}")
	print(f"{'A vs B':<32} {'mean_dA-B':>10} {'t':>7} {'A>B':>5} {'B>A':>5} {'minA':>7} {'minB':>7}")
	for a, b in itertools.combinations(names, 2):
		da = np.array([cells[a][i] for i in ids])
		db = np.array([cells[b][i] for i in ids])
		d = da - db
		t = d.mean() / (d.std(ddof=1) / np.sqrt(len(d)))
		print(f"{a+' vs '+b:<32} {d.mean():>10.4f} {t:>7.2f} {(d>0).sum():>5} {(d<0).sum():>5} {da.min():>7.3f} {db.min():>7.3f}")
	print("\nworst 6 cases per cell (id: min-margin):")
	for n in names:
		worst = sorted(cells[n].items(), key=lambda kv: kv[1])[:6]
		print(f"  {n:<16} " + "  ".join(f"{k}:{v:.2f}" for k, v in worst))

main(sys.argv[1:])
