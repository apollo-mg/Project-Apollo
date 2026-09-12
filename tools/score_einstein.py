#!/usr/bin/env python3
"""Score PREREG_EINSTEIN_TERMINATION.md (+ Amendments 1-3) mechanically.

Every verdict below is defined in the registration or in Amendment 3; nothing here is a judgement
call. The two things this scorer exists to make hard to get wrong:

  * 4 scored cells were previewed by the pilot (same seed). Every table is printed twice -- all
    cells, and with those 4 excluded -- and, given --pilot, whether they reproduced byte-for-byte.
  * Arms B and C are the same generation until the cap binds. The B-vs-C contrast is reported with
    its divergent-cell count and its outcome-differing count, not its row count.

Usage:
  ./venv_cachyos/bin/python3 tools/score_einstein.py data/receipts/viability/einstein_iq4 \
      --pilot data/receipts/viability/einstein_pilot/iq4xs --label "IQ4_XS primary"
"""
import argparse, glob, json, math, re, statistics as st, urllib.request
from collections import Counter
from pathlib import Path

CODING, IDEATION = ("E-C1", "E-C2"), ("E-I1", "E-I2")
PREVIEWED = {("E-C1", "A", 1), ("E-C1", "B", 1), ("E-I1", "A", 1), ("E-I1", "B", 1)}
KNOWN_INJECTIONS = ["Your thinking budget is exhausted", "Are you overthinking this?"]


def fisher(a, b, c, d):
    """Two-sided Fisher exact on [[a,b],[c,d]]: sum of every table at most as probable."""
    r1, r2, c1, n = a + b, c + d, a + c, a + b + c + d
    def p(x):
        return math.comb(r1, x) * math.comb(r2, c1 - x) / math.comb(n, c1)
    lo, hi = max(0, c1 - r2), min(r1, c1)
    obs = p(a)
    return min(1.0, sum(p(x) for x in range(lo, hi + 1) if p(x) <= obs * (1 + 1e-9)))


def load(d):
    rows = []
    for f in sorted(glob.glob(str(Path(d) / "arm*_rep*.jsonl"))):
        for line in open(f):
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return rows


def think(r):
    return len(r.get("reasoning") or "")


def nonterm(r):
    return r.get("finish") == "length"


def usable(r):                       # Amendment 3, P-E5
    return r.get("finish") == "stop" and bool((r.get("content") or "").strip())


def compliant(r):
    """The item's own done-condition. Reported beside P-E5, never inside it (Amendment 3)."""
    if not usable(r):
        return False
    c, i = r["content"].strip(), r["id"]
    if i == "E-C1":
        return bool(re.search(r"^\s*def \w+\(", c, re.M))
    if i == "E-C2":
        return bool(re.search(r"argparse|sys\.argv", c)) and "ignore" in c.lower()
    if i == "E-I1":
        lines = [re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", ln).strip() for ln in c.splitlines()]
        return len([ln for ln in lines if ln]) == 3
    if i == "E-I2":
        return len([p for p in re.split(r"\n\s*\n", c) if len(p.split()) >= 15]) == 2
    return False


def reasoning_tokens(r, tok_host):
    """Amendment 3, P-E2: an exact bound where decisive, tokenised where not, else unresolved."""
    ct = r.get("completion_tokens") or 0
    if ct < 5000:
        return "below", ct                       # completion bounds reasoning from above
    if not (r.get("content") or "").strip():
        return "exact", ct                       # empty answer: every token was reasoning
    if tok_host:
        try:
            req = urllib.request.Request(tok_host + "/tokenize",
                                         data=json.dumps({"content": r["content"]}).encode(),
                                         headers={"Content-Type": "application/json"})
            n = len(json.loads(urllib.request.urlopen(req, timeout=20).read())["tokens"])
            return "exact", ct - n
        except Exception:
            pass
    return "unresolved", None


def med(xs):
    return st.median(xs) if xs else float("nan")


def arm_table(rows, title):
    print(f"\n--- {title} ---")
    print(f"{'arm':4s} {'n':>3s} {'non-term':>9s} {'usable':>7s} {'compliant':>10s} "
          f"{'med think ch':>13s} {'med tokens':>11s}")
    for arm in "ABC":
        s = [r for r in rows if r["arm"] == arm]
        if not s:
            print(f"{arm:4s}   0   (no rows)")
            continue
        print(f"{arm:4s} {len(s):3d} {sum(map(nonterm, s)):9d} {sum(map(usable, s)):7d} "
              f"{sum(map(compliant, s)):10d} {med([think(r) for r in s]):13.0f} "
              f"{med([r.get('completion_tokens') or 0 for r in s]):11.0f}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root")
    ap.add_argument("--pilot", help="pilot dir, to check the 4 previewed cells reproduced")
    ap.add_argument("--label", default=None)
    ap.add_argument("--tokenize-host", default="http://127.0.0.1:8097")
    a = ap.parse_args()
    rows = load(a.root)
    label = a.label or Path(a.root).name
    print(f"=== {label}: {len(rows)} rows from {a.root} ===")

    # ---- instrument integrity -------------------------------------------------------------------
    print("\n=== Configuration as recorded per row (read from the server's /slots, not assumed) ===")
    for k in ("n_ctx", "kv_bpv", "n_predict", "model"):
        vals = Counter(str(r.get(k)) for r in rows)
        print(f"  {k:10s} {dict(vals)}" + ("   <-- INCONSISTENT" if len(vals) > 1 else ""))
    inj = [(r["arm"], r["id"], r["rep"]) for r in rows
           if any(m in (r.get("reasoning") or "") for m in KNOWN_INJECTIONS)]
    print(f"  injected budget text found in reasoning: {len(inj)} rows"
          + ("" if not inj else f"  {inj[:6]}  <-- thinking lengths must subtract it"))

    # ---- per-arm, both ways ---------------------------------------------------------------------
    clean = [r for r in rows if (r["id"], r["arm"], r["rep"]) not in PREVIEWED]
    arm_table(rows, f"ALL cells ({len(rows)})")
    arm_table(clean, f"EXCLUDING the 4 pilot-previewed cells ({len(clean)})")

    # ---- previewed-cell reproduction ------------------------------------------------------------
    if a.pilot:
        pil = {(r["id"], r["arm"], r["rep"]): r for r in load(a.pilot)}
        sc = {(r["id"], r["arm"], r["rep"]): r for r in rows}
        print("\n=== Did the 4 previewed cells reproduce? (a cross-process determinism check) ===")
        for key in sorted(PREVIEWED):
            p, s = pil.get(key), sc.get(key)
            if not p or not s:
                print(f"  {key}: {'no pilot row' if not p else 'no scored row yet'}")
                continue
            same = (p.get("reasoning"), p.get("content")) == (s.get("reasoning"), s.get("content"))
            print(f"  {key}: {'BYTE-IDENTICAL' if same else 'DIFFERS'}  "
                  f"pilot {p.get('completion_tokens')} tok / scored {s.get('completion_tokens')} tok")

    # ---- B vs C: the same generation until the cap binds ----------------------------------------
    b = {(r["id"], r["rep"]): r for r in rows if r["arm"] == "B"}
    c = {(r["id"], r["rep"]): r for r in rows if r["arm"] == "C"}
    both = sorted(set(b) & set(c))
    if both:
        ident = [k for k in both if (b[k].get("reasoning"), b[k].get("content"))
                 == (c[k].get("reasoning"), c[k].get("content"))]
        prefix = [k for k in both if k not in ident
                  and (b[k].get("reasoning") or "").startswith((c[k].get("reasoning") or "")[:-8])]
        outdiff = [k for k in both if (nonterm(b[k]), usable(b[k])) != (nonterm(c[k]), usable(c[k]))]
        print(f"\n=== B vs C: {len(both)} paired cells ===")
        print(f"  byte-identical (cap never bound)       {len(ident)}  <- no information about the cap")
        print(f"  C's thinking is a truncation of B's     {len(prefix)}  <- the cap bound; same trajectory")
        print(f"  outcome differs (non-term or usable)    {len(outdiff)}  <- the real n for P-E4 vs P-E3")
        for k in outdiff:
            print(f"    {k}: B finish={b[k]['finish']} usable={usable(b[k])} | "
                  f"C finish={c[k]['finish']} usable={usable(c[k])}")

    # ---- predictions ----------------------------------------------------------------------------
    A = [r for r in rows if r["arm"] == "A"]
    B = [r for r in rows if r["arm"] == "B"]
    C = [r for r in rows if r["arm"] == "C"]

    def v(ok):
        return "CONFIRMED" if ok else "FALSIFIED"

    print("\n=== Predictions (all cells; see the excluded table above for the 4-cell sensitivity) ===")
    if A and B:
        mA, mB = med([think(r) for r in A]), med([think(r) for r in B])
        print(f"  P-E1  B median thinking > A          {mB:.0f} vs {mA:.0f} ch  -> {v(mB > mA)}")
    if B:
        res = [reasoning_tokens(r, a.tokenize_host) for r in B]
        hit = sum(1 for kind, n in res if kind == "exact" and n >= 5000)
        unres = sum(1 for kind, _ in res if kind == "unresolved")
        half = len(B) / 2
        if hit + unres < half:
            verdict = "CONFIRMED"
        elif hit >= half:
            verdict = "FALSIFIED"
        else:
            verdict = "UNRESOLVED (unresolved rows could flip it)"
        print(f"  P-E2  B reaches >=5000 reasoning tok  {hit}/{len(B)} (+{unres} unresolved), "
              f"'fewer than half' -> {verdict}")
    if A and B:
        nA, nB = sum(map(nonterm, A)), sum(map(nonterm, B))
        print(f"  P-E3  B non-term > A                  {nB}/{len(B)} vs {nA}/{len(A)}  -> {v(nB > nA)}  "
              f"(Fisher p={fisher(nB, len(B) - nB, nA, len(A) - nA):.3f})")
    if C:
        nC = sum(map(nonterm, C))
        print(f"  P-E4  C non-term == 0                 {nC}/{len(C)}  -> {v(nC == 0)}")
        uC = sum(map(usable, C))
        print(f"  P-E5  C usable >= 80%                 {uC}/{len(C)} = {uC / len(C):.0%}  -> {v(uC / len(C) >= 0.8)}")
    nt = [r for r in rows if nonterm(r)]
    if not nt:
        print("  P-E6  runaway is inside <think>       no non-terminating generation in any arm -> UNSCOREABLE")
    else:
        inside = sum(1 for r in nt if not (r.get("content") or "").strip())
        print(f"  P-E6  runaway is inside <think>       {inside}/{len(nt)} with empty answer  -> {v(inside == len(nt))}")
    if A and B:
        def ratio(items):
            ta = [think(r) for r in A if r["id"] in items]
            tb = [think(r) for r in B if r["id"] in items]
            return med(tb) / med(ta) if ta and tb and med(ta) else float("nan")
        rc, ri = ratio(CODING), ratio(IDEATION)
        print(f"  P-E7  ideation overrun > coding       B/A ratio ideation {ri:.2f}x vs coding {rc:.2f}x  "
              f"-> {v(ri > rc)}  (pilot already pointed this way: little independent weight)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
