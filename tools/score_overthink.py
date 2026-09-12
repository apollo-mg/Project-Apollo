#!/usr/bin/env python3
"""Score an overthink-injection run (arms A/B/C) and measure its own effective sample size.

Written 2026-09-12. The IQ3_M run taught the lesson this tool exists to enforce: with a fixed
server seed, arms A/B/C are THE SAME GENERATION until the thinking cap actually binds. Where it
never binds the three arms are byte-identical, so those cells carry no information about the arm
contrast at all. The IQ3_M run had 24 cells per arm and an effective n of 3.

Any A-vs-B-vs-C claim must therefore be read against the divergent-cell count, not the row count.
This computes it from the generations themselves rather than assuming it.

  arm A  unrestricted thinking
  arm B  bare thinking cap (reasoning_budget_tokens)
  arm C  cap + the injected "are you overthinking?" message

Usage:
  ./venv_cachyos/bin/python3 tools/score_overthink.py data/receipts/viability/overthink_q6k
  ./venv_cachyos/bin/python3 tools/score_overthink.py data/receipts/viability/overthink --label IQ3_M
"""
import argparse, glob, json, math, re, statistics as st
from collections import Counter, defaultdict
from pathlib import Path

FAIL = {"ANSWERED-WRONG", "NO-STOP/REC"}          # on the unanswerable arm, abstaining is correct
REP = re.compile(r"arm([ABC])_rep(\d+)\.jsonl$")

# The budget message is delivered INTO the reasoning stream, so it is counted as "thinking" by any
# naive len(reasoning). These are the exact strings from overthink_run.sh; subtracting them is the
# difference between measuring the model's deliberation and measuring our own prompt.
INJECT = {
    "B": "Your thinking budget is exhausted. Answer now.",
    "C": ("Are you overthinking this? Check: have you FOUND this, or are you building it? If the "
          "premise is false or the fact does not exist, answer UNKNOWN — that is a correct answer, "
          "not a failure. If you genuinely cannot resolve it either way, answer ADVISOR and then "
          "state, in one or two sentences, exactly what is blocking you and what you would ask an "
          "advisor. ADVISOR without that explanation is a failure, and ADVISOR leaves the task "
          "INCOMPLETE either way. Remember the meta goal. Speed ≠ goodness."),
}


def think_chars(r):
    """Length of the model's own reasoning, with any injected budget message removed."""
    s = r.get("reasoning") or ""
    msg = INJECT.get(r["_arm"])
    return len(s) - s.count(msg) * len(msg) if msg else len(s)


def fisher(a, b, c, d):
    """Two-sided Fisher exact on [[a,b],[c,d]]. Sums every table at most as probable."""
    def p(x):
        r1, r2, c1, n = a + b, c + d, a + c, a + b + c + d
        return (math.comb(r1, x) * math.comb(r2, c1 - x)) / math.comb(n, c1)
    lo, hi = max(0, a + c - (c + d)), min(a + b, a + c)
    obs = p(a)
    return min(1.0, sum(p(x) for x in range(lo, hi + 1) if p(x) <= obs * (1 + 1e-9)))


def load(root):
    rows = []
    for f in sorted(glob.glob(str(Path(root) / "arm*_rep*.jsonl"))):
        m = REP.search(f)
        if not m:
            continue
        for line in open(f):
            r = json.loads(line)
            r["_arm"], r["_rep"] = m.group(1), int(m.group(2))
            rows.append(r)
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root")
    ap.add_argument("--label", default=None)
    a = ap.parse_args()
    label = a.label or Path(a.root).name
    rows = load(a.root)
    print(f"=== {label}: {len(rows)} generations from {a.root} ===\n")

    for arm_kind in ("unanswerable", "answerable"):
        sel = [r for r in rows if r["arm"] == arm_kind]
        print(f"--- {arm_kind} arm ({len(sel)//3} cells per arm) ---")
        print(f"{'arm':4s} {'ABSTAIN':>8s} {'WRONG':>6s} {'NO-STOP':>8s} {'CORRECT':>8s} {'fail':>7s} "
              f"{'med think':>10s} {'tot raw':>9s} {'tot own':>9s} {'injected':>9s}")
        for arm in "ABC":
            s = [r for r in sel if r["_arm"] == arm]
            c = Counter(r["status"] for r in s)
            raw = sum(len(r.get("reasoning") or "") for r in s)
            own = [think_chars(r) for r in s]
            fails = sum(c[k] for k in FAIL)
            print(f"{arm:4s} {c['ABSTAINED']:8d} {c['ANSWERED-WRONG']:6d} {c['NO-STOP/REC']:8d} "
                  f"{c['ANSWERED-CORRECT']:8d} {str(fails)+'/'+str(len(s)):>7s} "
                  f"{st.median(own):10.0f} {raw:9d} {sum(own):9d} {raw-sum(own):9d}")
        print("  'tot own' removes the injected budget message, which the server delivers INTO the")
        print("  reasoning stream and which len(reasoning) therefore counts as the model thinking.")
        print()

    # ---- the part that decides whether any of the above means anything -------------------------
    un = [r for r in rows if r["arm"] == "unanswerable"]
    cells = defaultdict(dict)
    for r in un:
        cells[(r["id"], r["_rep"])][r["_arm"]] = r
    ident, diverge = [], []
    for key, byarm in sorted(cells.items()):
        if len(byarm) < 3:
            continue
        sigs = {arm: (r.get("reasoning") or "", r.get("content") or "") for arm, r in byarm.items()}
        (ident if len(set(sigs.values())) == 1 else diverge).append((key, byarm))

    n_cells = len(cells)
    print(f"=== Effective sample size: the arms are one generation until the cap binds ===")
    print(f"  cells total                 {n_cells}")
    print(f"  byte-identical across A/B/C {len(ident)}  <- carry ZERO information about the arm contrast")
    print(f"  divergent                   {len(diverge)}  <- the real n for any A-vs-B-vs-C claim")
    if ident:
        c = Counter(next(iter(b.values()))["status"] for _, b in ident)
        fails = sum(c[k] for k in FAIL)
        print(f"\n  The identical cells, scored once (they are the same generation three times):")
        print(f"    ABSTAINED {c['ABSTAINED']}  ANSWERED-WRONG {c['ANSWERED-WRONG']}  "
              f"NO-STOP/REC {c['NO-STOP/REC']}  -> {fails} failures baked into all three arms")
    # Byte-divergence only means the cap bound. What carries the contrast is a changed OUTCOME.
    status_diff = [(k, b) for k, b in diverge if len({b[x]["status"] for x in "ABC"}) > 1]
    print(f"\n  of those, cells where the OUTCOME actually changed: {len(status_diff)}")
    print("  (a cell where the cap bound but all three arms still abstained tells you the cap did")
    print("   no harm; it cannot tell you the message did any good)")
    if status_diff:
        print(f"\n    {'item':10s} {'rep':>3s}  {'A':<16s} {'B':<16s} {'C':<16s}")
        for (i, rep), b in status_diff:
            print(f"    {i:10s} {rep:3d}  " + " ".join(f"{b[x]['status']:<16s}" for x in "ABC"))
    for x, y in (("A", "B"), ("B", "C"), ("A", "C")):
        n = sum(1 for _, b in cells.items() if len(b) == 3 and b[x]["status"] != b[y]["status"])
        print(f"    {x} vs {y}: {n} of {n_cells} cells differ in outcome"
              + ("   <- the contrast has NO cells to stand on" if n == 0 else ""))
    wrong_ident = sum(1 for _, b in ident if next(iter(b.values()))["status"] == "ANSWERED-WRONG")
    if wrong_ident:
        print(f"\n  {wrong_ident} of the ANSWERED-WRONG cells are in the byte-identical set: the same")
        print("  generation counted once per arm. No arm could have affected them.")

    print("\n=== Fisher exact on the unanswerable arm (all cells, as pre-registered) ===")
    f = {}
    for arm in "ABC":
        s = [r for r in un if r["_arm"] == arm]
        f[arm] = (sum(r["status"] in FAIL for r in s), len(s))
    for x, y in (("C", "A"), ("C", "B"), ("B", "A")):
        fx, nx = f[x]
        fy, ny = f[y]
        print(f"  {x} {fx}/{nx} vs {y} {fy}/{ny}   p = {fisher(fx, nx-fx, fy, ny-fy):.3f}")
    print(f"  total failure events across all three arms: {sum(v[0] for v in f.values())}")

    print("\n=== ADVISOR escape hatch ===")
    # Must be checked on the ANSWER, never on reasoning+content: arm C's injected message contains
    # the word ADVISOR and is delivered into the reasoning stream, so a blob match finds the prompt
    # echoing back and reports an emission that never happened.
    adv = [r for r in rows if (r.get("got") or "").strip().upper() == "ADVISOR"]
    echo = sum(1 for r in rows if "ADVISOR" in (r.get("reasoning") or ""))
    print(f"  emitted AS THE ANSWER in {len(adv)} of {len(rows)} generations"
          + ("  -> P-O7/P-O8 UNSCOREABLE" if not adv else ""))
    print(f"  the word appears in the reasoning of {echo} rows -- that is our own injected message,")
    print("  not the model escalating. Scoring it as an emission would be a false positive.")
    for arm_kind in ("unanswerable", "answerable"):
        for arm in "ABC":
            s = {(r.get("got") or "").strip() for r in rows
                 if r["arm"] == arm_kind and r["_arm"] == arm}
            print(f"  distinct answers, {arm_kind:12s} arm {arm}: {sorted(s)}")

    print("\n=== Configuration recorded per row (what a future comparison can verify) ===")
    for k in ("effort", "n_ctx", "model", "host", "budget_tokens", "sampling"):
        vals = Counter(str(r[k]) for r in rows if k in r)
        n = sum(vals.values())
        flag = "" if n in (0, len(rows)) else "   <- PARTIAL: recorded mid-run, not for every row"
        print(f"  {k:14s} {n:3d}/{len(rows)} rows  {dict(vals) if vals else '(absent)'}{flag}")
    # Same recovery rule as tools/compare_runs.py: the runner sets the escalated retry to
    # min(n_predict*2, n_ctx-1024), so a retry BELOW the 2x ceiling pins n_ctx exactly and a retry
    # AT the ceiling only bounds it. Reporting a bound as an exact value is how the CAL baseline
    # comparison went wrong in the first place.
    ev = set()
    for r in rows:
        att = r.get("attempts") or []
        if len(att) >= 2:
            first, second = att[0][0], att[1][0]
            ev.add(second + 1024 if second < first * 2 else f">={second + 1024}")
    print(f"  implied n_ctx from escalated-retry budgets: {sorted(map(str, ev)) or '(none escalated)'}")
    if any(str(x).startswith(">=") for x in ev):
        print("    a '>=' is a LOWER BOUND, not a measurement: the retry hit the 2x ceiling, so the")
        print("    headroom never constrained it. Use the recorded n_ctx field where present.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
