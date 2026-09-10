#!/usr/bin/env python3
"""Score the cache-reuse A/B against PREREG_CACHE_REUSE_AB.md.

Mechanical on purpose: the predictions were written before the run, and reading results by eye is
how you talk yourself into the answer you expected. Every number here traces to a file on disk.
"""
import glob, json, os, re, sys, collections

OUT = "/mnt/TG_2TB/Projects/Apollo/data/receipts/viability/cache-ab"
BENCH = "/home/mark/projects/hermes-bench-tool-call"
ORDER = [l.strip() for l in open("/tmp/tasklist.txt") if l.strip()][:22]


def results(tag):
    """status by task id, in the prereg's execution order."""
    rd = f"{BENCH}/results/cacheab_{tag}"
    by = {}
    for f in glob.glob(rd + "/*.json"):
        b = os.path.basename(f)
        if b == "summary.json":
            continue
        m = re.match(r"(t\d+_[a-z_]+?)_(t\d+_[a-z_0-9]+)$", b[:-5])
        if m:
            by[m.group(1) + "/" + m.group(2)] = json.load(open(f)).get("status")
    return [(t, by.get(t)) for t in ORDER]


def wire(tag):
    p = f"{OUT}/wire_{tag}.jsonl"
    if not os.path.exists(p):
        return []
    out = []
    for l in open(p):
        try:
            out.append(json.loads(l))
        except Exception:
            pass
    return out


def runaways(tag):
    """calls that hit the output cap -- the actual failure, independent of harness bookkeeping."""
    return [d for d in wire(tag)
            if d.get("ev") in ("response", "aborted") and d.get("finish_reason") == "length"]


def degenerate(text, n=60):
    """crude repetition check: fraction of the tail made of the single most common 40-char shingle."""
    t = (text or "")[-8000:]
    if len(t) < 400:
        return None, 0.0
    sh = collections.Counter(t[i:i + 40] for i in range(0, len(t) - 40, 7))
    top, cnt = sh.most_common(1)[0]
    frac = cnt * 7 / max(1, len(t))
    return top, frac


def main():
    print("=" * 78)
    for tag in ("ctrl", "treat"):
        rows = results(tag)
        done = [r for r in rows if r[1]]
        c = collections.Counter(r[1] for r in done)
        ra = runaways(tag)
        print(f"\n### ARM {tag} ({len(done)}/22 tasks recorded)   {dict(c)}")
        for i, (t, s) in enumerate(rows, 1):
            if s:
                mark = "  <-- v5 onset position" if i == 17 else ""
                print(f"   {i:2d} {t:42s} {s}{mark}")
        post = [s for i, (t, s) in enumerate(rows, 1) if i >= 17 and s]
        bad = sum(1 for s in post if s == "INFRA_ERROR")
        print(f"   tasks 17-22 recorded: {len(post)}   INFRA_ERROR: {bad}")
        print(f"   wire: {len(ra)} generations hit finish_reason='length'")

        # P-C3: does the system prompt drift within an arm?
        shas = [d.get("sys_sha") for d in wire(tag) if d.get("ev") == "request" and d.get("sys_sha")]
        u = sorted(set(shas))
        print(f"   sys_sha across {len(shas)} chat requests: {len(u)} distinct {u[:4]}")

    # P-C1 / P-C2
    cb = sum(1 for i, (t, s) in enumerate(results("ctrl"), 1) if i >= 17 and s == "INFRA_ERROR")
    tb = sum(1 for i, (t, s) in enumerate(results("treat"), 1) if i >= 17 and s == "INFRA_ERROR")
    print("\n" + "=" * 78)
    print(f"P-C1 (75%): CTRL reproduces onset       -> {cb}/6 runaways past #17 "
          f"{'CONFIRMED' if cb >= 3 else 'FALSIFIED' if cb <= 2 else '?'}")
    print(f"P-C2 (45%): TREAT suppresses it         -> {tb}/6 "
          f"{'CONFIRMED' if tb <= 1 else 'FALSIFIED' if abs(tb - cb) <= 1 else 'PARTIAL'}")

    # P-C4: is the runaway text degenerate?
    print("\nP-C4 (50%): runaway text character")
    for tag in ("ctrl", "treat"):
        for d in runaways(tag)[:2]:
            top, frac = degenerate(d.get("text", ""))
            if top is None:
                print(f"   {tag}: too short to judge ({d.get('text_chars')} chars)")
            else:
                print(f"   {tag}: {d.get('text_chars')} chars, top-shingle share {frac:.1%}"
                      f"  {'DEGENERATE' if frac > 0.25 else 'not obviously looping'}")
                print(f"        tail: {repr(d.get('text','')[-160:])}")


if __name__ == "__main__":
    main()
