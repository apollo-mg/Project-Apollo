#!/usr/bin/env python3
"""Score the blind pelican judging exactly as PREREG_BLIND_ART.md and its two addenda specify.

Inputs: the sealed mapping (hash-checked against the prereg), Mark's picks exported from the page's
store (one JSON per pair), and outside raters' exported text. Written before any pick was visible;
run once. Anything not in the prereg is printed under DESCRIPTIVE and carries no verdict.
"""
import glob, hashlib, itertools, json, math, re, statistics, sys
from pathlib import Path

ROOT = Path("/mnt/TG_2TB/Projects/Apollo")
D = ROOT / "data/receipts/svgbench-blind"
MAPPING = D / "MAPPING_SEALED.json"
SEALED_SHA = "cd1d4f46a6b160ab45461f1875e2f4e2bd187838153551c1a978bb03158764e9"
Q2 = ("UD-Q2_K_XL", "UD-IQ2_M")
Q4 = ("UD-IQ4_XS", "UD-Q4_K_M")
MIN_FIRST, MIN_REV, MIN_REP, CLICK_THROUGH_S = 40, 18, 6, 1.5

raw = MAPPING.read_bytes()
if hashlib.sha256(raw).hexdigest() != SEALED_SHA:
    sys.exit("MAPPING HASH MISMATCH -- the mapping changed after the prereg; stopping")
MP = json.loads(raw)
DRAW, PAIRS = MP["drawings"], {p["id"]: p for p in MP["pairs"]}
FIRST = sorted(c for c, v in DRAW.items() if v["step"] == "p1")


def label(c):
    v = DRAW[c]
    return f"{v['quant']} r{v['rep']} {v['step']}"


# ---------- loading ----------
def load_mark(folder):
    J, ms, bad = {}, [], []
    for f in sorted(glob.glob(str(folder / "**" / "*.json"), recursive=True)):
        d = json.load(open(f))
        d = d.get("data", d) if isinstance(d, dict) and isinstance(d.get("data"), dict) else d
        pid, ch = d.get("pair") or Path(f).stem, d.get("choice")
        if pid in PAIRS and {d.get("a"), d.get("b")} != set(PAIRS[pid]["pair"]):
            bad.append(f"{pid}: stored codes {d.get('a')},{d.get('b')} do not match the mapping")
        w = d.get("a") if ch == "a" else d.get("b") if ch == "b" else "=" if ch == "tie" else None
        J[pid] = (w, bool(d.get("seen")), d.get("a"))       # third field: the code shown on the left
        if isinstance(d.get("ms"), (int, float)):
            ms.append(d["ms"])
    return J, (statistics.median(ms) / 1000 if ms else None), bad


def load_export(path):
    lines = Path(path).read_text().strip().splitlines()
    head = lines[0]
    m, s = re.search(r"median ([0-9.]+)s", head), re.search(r"seed (\S+)", head)
    J = {}
    for tok in " ".join(lines[1:]).split():
        pid, _, w = tok.partition(":")
        J[pid] = (w.rstrip("*"), w.endswith("*"), None)
    return J, (float(m.group(1)) if m else None), head, (s.group(1) if s else None)


def integrity(J):
    bad = []
    for pid, (w, _, _) in J.items():
        if pid not in PAIRS:
            bad.append(f"{pid}: no such pair")
        elif w != "=" and w not in PAIRS[pid]["pair"]:
            bad.append(f"{pid}: winner {w} is not in the pair")
    return bad


# ---------- the prereg's rules ----------
def first_values(J):
    """Value per distinct first-drawing pair, from the lexically smaller code's side.
    Win 1 / too close 0.5 / loss 0; a repeated pair enters once at the mean of its judgments;
    flagged judgments are dropped (a pair with every judgment flagged drops out)."""
    acc = {}
    for pid, p in PAIRS.items():
        src = PAIRS[p["repeat_of"]] if p["kind"] == "repeat" else p
        if src["kind"] != "first" or pid not in J:
            continue
        w, flagged, _ = J[pid]
        if flagged or w is None:
            continue
        x, y = sorted(p["pair"])
        acc.setdefault((x, y), []).append(1.0 if w == x else 0.0 if w == y else 0.5)
    return {k: sum(v) / len(v) for k, v in acc.items()}


def win_rates(vals):
    tot, n = {}, {}
    for (x, y), v in vals.items():
        for d, s in ((x, v), (y, 1 - v)):
            tot[d] = tot.get(d, 0.0) + s
            n[d] = n.get(d, 0) + 1
    return {d: tot[d] / n[d] for d in tot}


def cross_stat(rates, q4):
    q2 = [c for c in FIRST if c not in q4]
    return sum(1.0 if rates[b] > rates[a] else 0.5 if rates[b] == rates[a] else 0.0 for a in q2 for b in q4)


def perm_test(rates):
    true_q4 = [c for c in FIRST if DRAW[c]["quant"] in Q4]
    obs = cross_stat(rates, true_q4)
    stats = [cross_stat(rates, list(q4)) for q4 in itertools.combinations(FIRST, len(true_q4))]
    p = sum(1 for s in stats if abs(s - 12) >= abs(obs - 12) - 1e-9) / len(stats)
    return obs, p, len(stats)


def sign_p(k, n):
    if n == 0:
        return None
    t = sum(math.comb(n, j) for j in range(0, min(k, n - k) + 1)) / 2 ** n
    return min(1.0, 2 * t)


def fisher_p(a, b, c, d):
    r1, r2, c1, n = a + b, c + d, a + c, a + b + c + d
    if n == 0 or r1 == 0 or r2 == 0:
        return None
    pr = lambda x: math.comb(r1, x) * math.comb(r2, c1 - x) / math.comb(n, c1)
    p0 = pr(a)
    return min(1.0, sum(pr(x) for x in range(max(0, c1 - r2), min(r1, c1) + 1) if pr(x) <= p0 * (1 + 1e-9)))


def verdict(ok, evaluable):
    return "NOT EVALUABLE (incomplete)" if not evaluable else ("CONFIRMED" if ok else "FALSIFIED")


def analyse(name, J):
    print(f"\n==================== {name} ====================")
    vals = first_values(J)
    rates = win_rates(vals)
    obs, p, nperm = perm_test(rates) if len(rates) == len(FIRST) else (None, None, 0)
    ev1 = len(vals) >= MIN_FIRST and obs is not None
    print(f" first-drawing pairs usable: {len(vals)}/45")
    print(" first-drawing win rates (labels unsealed):")
    for c in sorted(rates, key=lambda c: -rates[c]):
        print(f"   {c}  {rates[c]:.3f}  {label(c)}  [{'Q4' if DRAW[c]['quant'] in Q4 else 'Q2'}]")
    if obs is not None:
        print(f" P-B1 (70%) no separation Q2 vs Q4: Q4 ahead in {obs:g}/24, exact permutation p = {p:.3f} "
              f"({nperm} label sets) -> {verdict(p >= 0.05, ev1)}")
        print(f" P-B2 (55%) Q4 ahead in more than 12 of 24: {obs:g} -> {verdict(obs > 12, ev1)}")

    rev = [p_ for p_ in PAIRS.values() if p_["kind"] == "revision"]
    usable = [(p_, J[p_["id"]][0]) for p_ in rev if p_["id"] in J and not J[p_["id"]][1] and J[p_["id"]][0]]
    dec = [(p_, w) for p_, w in usable if w != "="]
    kc = sum(w == p_["child"] for p_, w in dec)
    ev3 = len(usable) >= MIN_REV
    print(f" revision pairs usable: {len(usable)}/22, decisive {len(dec)}, ties {len(usable) - len(dec)}")
    if dec:
        print(f" P-B3 (65%) child preferred in > half of decisive: {kc}/{len(dec)}, sign test p = {sign_p(kc, len(dec)):.3f} "
              f"-> {verdict(kc / len(dec) > 0.5, ev3)}")
    g = [(p_, w) for p_, w in dec if p_["framing"] == "goal"]
    i = [(p_, w) for p_, w in dec if p_["framing"] == "intent"]
    gk, ik = sum(w == p_["child"] for p_, w in g), sum(w == p_["child"] for p_, w in i)
    if g and i:
        fp = fisher_p(gk, len(g) - gk, ik, len(i) - ik)
        print(f" P-B4 (50%) goal child-rate > intent child-rate: goal {gk}/{len(g)} vs intent {ik}/{len(i)}, "
              f"Fisher p = {fp:.3f} -> {verdict(gk / len(g) > ik / len(i), ev3)}")

    reps = [p_ for p_ in PAIRS.values() if p_["kind"] == "repeat"]
    both = [(p_, J[p_["id"]][0], J[p_["repeat_of"]][0]) for p_ in reps
            if p_["id"] in J and p_["repeat_of"] in J and not J[p_["id"]][1] and not J[p_["repeat_of"]][1]]
    agree = sum(a == b for _, a, b in both)
    print(f" P-B5 (70%) >= 6 of 8 repeats agree: {agree}/{len(both)} usable -> {verdict(agree >= 6, len(both) >= MIN_REP)}")
    return vals, rates, usable


def agreement(va, vb):
    keys = [k for k in va if k in vb and va[k] != 0.5 and vb[k] != 0.5]
    same = sum((va[k] > 0.5) == (vb[k] > 0.5) for k in keys)
    return same, len(keys)


def fnv(s):
    h = 0x811C9DC5
    for ch in s:
        h = ((h ^ ord(ch)) * 0x01000193) & 0xFFFFFFFF
    return h


def left_code(pid, seed):
    """The code the share page showed on the left for this rater (same rule as the page's sides())."""
    a, b = PAIRS[pid]["pair"]
    k = a + b if a < b else b + a
    return b if fnv(seed + k) & 1 else a


def main():
    mark_dir = D / "picks_mark"
    Jm, med_m, bad_m = load_mark(mark_dir)
    bad_m += integrity(Jm)
    print(f"mapping sha256 OK ({SEALED_SHA[:12]}...), {len(DRAW)} drawings, {len(PAIRS)} pairs")
    print(f"Mark: {len(Jm)}/75 picks, median decision {med_m:.1f}s, flagged {sum(f for _, f, _ in Jm.values())}, "
          f"integrity problems {len(bad_m)}{': ' + '; '.join(bad_m[:3]) if bad_m else ''}")
    raters = {}
    for f in sorted((D / "raters").glob("*_export.txt")):
        J, med, head, seed = load_export(f)
        bad = integrity(J)
        print(f"{f.stem}: {len(J)}/75 picks, median {med}s, integrity problems {len(bad)}  | {head[:60]}")
        if bad:
            print("   SET ASIDE: " + "; ".join(bad[:5]))
            continue
        if med is not None and med < CLICK_THROUGH_S:
            print(f"   EXCLUDED: median {med}s < {CLICK_THROUGH_S}s click-through rule")
            continue
        raters[f.stem] = (J, seed)

    vm, rm, um = analyse("MARK (primary, as pre-registered)", Jm)
    rv = {}
    for name, (J, seed) in raters.items():
        rv[name] = analyse(f"{name} (secondary; human/machine status unconfirmed)", J)

    print("\n==================== outside raters vs Mark ====================")
    for name, (v, r, u) in rv.items():
        same, n = agreement(vm, v)
        print(f" P-B6 (55%) {name} agrees with Mark on > 60% of decisive first-drawing pairs: "
              f"{same}/{n} = {same / n:.2f} -> {'CONFIRMED' if same / n > 0.6 else 'FALSIFIED'} "
              f"[counts only if {name} is confirmed human]" if n else f" {name}: no shared decisive pairs")
    if rv:
        pooled = {c: statistics.mean([rm[c]] + [r[c] for (_, r, _) in rv.values()]) for c in FIRST}
        obs, p, _ = perm_test(pooled)
        print(f" P-B7 (75%) pooled (Mark + {', '.join(rv)}) does not separate: Q4 ahead in {obs:g}/24, p = {p:.3f} "
              f"-> {'CONFIRMED' if p >= 0.05 else 'FALSIFIED'} [if every outside rater is human; "
              f"otherwise NOT EVALUABLE -- fewer than two eligible raters]")

    print("\n==================== DESCRIPTIVE (not pre-registered) ====================")
    if rv:
        for name, (v, r, u) in rv.items():
            xs, ys = [rm[c] for c in FIRST], [r[c] for c in FIRST]
            rank = lambda a: [sorted(a).index(x) + (sorted(a).count(x) - 1) / 2 for x in a]
            rx, ry = rank(xs), rank(ys)
            mx, my = statistics.mean(rx), statistics.mean(ry)
            num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
            den = math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)) or 1
            print(f" Spearman rho, first-drawing win rates, Mark vs {name}: {num / den:+.2f} (n = 10)")
    dm = [(pid, w, L) for pid, (w, f, L) in Jm.items() if w not in (None, "=") and not f]
    print(f" side: Mark picked the LEFT drawing in {sum(w == L for _, w, L in dm)}/{len(dm)} decisive picks")
    for name, (J, seed) in raters.items():
        dj = [(pid, w) for pid, (w, f, _) in J.items() if w != "=" and not f and pid in PAIRS]
        print(f" side: {name} picked the LEFT drawing in {sum(w == left_code(pid, seed) for pid, w in dj)}/{len(dj)} decisive picks")
    print(" revision pairs (parent -> child), who each rater preferred:")
    sys.path.insert(0, str(ROOT / "tools/svgbench"))
    import explore_ladder as E
    src = ROOT / "data/receipts/svgbench-ladder"
    for p_ in sorted((p_ for p_ in PAIRS.values() if p_["kind"] == "revision"), key=lambda p_: label(p_["child"])):
        ch = E.change(src / DRAW[p_["parent"]]["png"], src / DRAW[p_["child"]]["png"])
        says = lambda J: "—" if p_["id"] not in J else ("tie" if J[p_["id"]][0] == "=" else
                                                       "child" if J[p_["id"]][0] == p_["child"] else "parent")
        extra = "  ".join(f"{n}:{says(J):6s}" for n, (J, _) in raters.items())
        print(f"   {label(p_['child']):26s} change {ch['changed_of_union']:.3f}  Mark:{says(Jm):6s} {extra}")


if __name__ == "__main__":
    main()
