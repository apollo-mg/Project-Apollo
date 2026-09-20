#!/usr/bin/env python3
"""Have we already answered this? Run BEFORE designing an experiment.

    ./tools/ledger_precheck.py "prompt cache determinism"
    ./tools/ledger_precheck.py "MTP nondeterminism" --deep    # + semantic search over receipts

WHY THIS EXISTS
---------------
data/receipts/INDEX.md was created on 2026-08-16 after a day of work re-derived six things
already sitting in the receipts directory. Its instruction is "Grep this file before designing
anything."

On 2026-09-20 it happened again, to the same finding. A session spent several hours establishing
that prompt-cache reuse plus MTP makes generation non-deterministic, and that `cache_prompt:false`
fixes it. Both were already in INDEX.md:

    MTP is deterministic at temp 0. The instability was MTP x prompt-caching, not MTP
      -> battle16gb/MTP_CACHEPROMPT_FALSIFICATION.md   (07-30)
    Prefix-cache reuse changes temp-0 output on genuine upstream; cache_prompt=true is DEFAULT
      -> hermesagent20/PREFIX_CACHE_CHANGES_OUTPUT.md  (07-27)

The index was not at fault; it held the answer. **The rule lived inside the file nobody opens.**
A discipline with nothing to trigger it is not a control. This is the trigger: one cheap command,
referenced from CLAUDE.md, which is what actually gets read at the start of a session.

Exit codes: 0 = no prior art found, 2 = PRIOR ART FOUND (so it can gate a script).
"""
import argparse, re, sys, subprocess
from pathlib import Path

ROOT = Path("/mnt/TG_2TB/Projects/Apollo")
INDEX = ROOT / "data/receipts/INDEX.md"
FAILMODES = ROOT / "data/receipts/FAILURE_MODES.md"
RECEIPTS = ROOT / "data/receipts"

STOP = {"the","a","an","of","and","or","to","in","on","is","are","was","were","be","do","does",
        "did","how","why","what","when","we","our","it","its","for","with","at","by","from",
        "this","that","can","could","should","would","have","has","had"}

def terms(q):
    return [w for w in re.findall(r"[a-zA-Z_][a-zA-Z0-9_.-]{2,}", q.lower()) if w not in STOP]

def scan(path, words, label):
    """Line-level scan. A line matching >=2 distinct query terms is a hit; with one term it must
    be a rarer word, or every query about 'cache' returns the whole file."""
    if not path.exists():
        return []
    hits = []
    for n, line in enumerate(path.read_text(errors="replace").splitlines(), 1):
        low = line.lower()
        matched = {w for w in words if w in low}
        if len(matched) >= 2 or (len(matched) == 1 and len(next(iter(matched))) >= 7):
            if line.strip() and not line.strip().startswith(("#", "---", "**Why", "| finding")):
                hits.append((label, n, line.strip(), len(matched)))
    hits.sort(key=lambda h: -h[3])
    return hits

def main(a):
    words = terms(a.query)
    if not words:
        print("give me some words to look for", file=sys.stderr); return 1
    print(f"terms: {' '.join(words)}\n")

    found = False
    for path, label in [(INDEX, "INDEX.md"), (FAILMODES, "FAILURE_MODES.md")]:
        hits = scan(path, words, label)[: a.k]
        if hits:
            found = True
            print(f"=== {label} ===")
            for lbl, n, line, score in hits:
                print(f"  [{score} terms] L{n}: {line[:300]}")
            print()

    # Receipt filenames are a cheap second signal: they are named after the experiment, so a
    # matching name means someone ran this exact thing.
    names = []
    for p in RECEIPTS.rglob("*.md"):
        stem = p.stem.lower().replace("_", " ").replace("-", " ")
        if sum(1 for w in words if w in stem) >= 2:
            names.append(p.relative_to(ROOT))
    if names:
        found = True
        print("=== receipts whose FILENAME matches (named after the experiment) ===")
        for p in sorted(names)[: a.k]:
            print(f"  {p}")
        print()

    if a.deep:
        print("=== semantic search over receipts + ledger ===")
        try:
            r = subprocess.run([str(ROOT / "venv_cachyos/bin/python3"),
                                str(ROOT / "tools/ledger_query.py"), a.query,
                                "-k", str(a.k), "--all", "--chars", "300"],
                               capture_output=True, text=True, timeout=180)
            out = (r.stdout or r.stderr).strip()
            print(out[:2500] if out else "  (no output)")
            if r.stdout.strip():
                found = True
        except Exception as e:
            print(f"  semantic search unavailable: {type(e).__name__}: {e}")
        print()

    if found:
        print("PRIOR ART FOUND -- read the receipts above BEFORE designing the experiment.")
        print("If you still run it, say in the new receipt what it adds to the old one.")
        return 2
    print("No prior art found for those terms. Try --deep, or different words, before concluding")
    print("this is new -- 588 receipts across 87 directories are named after experiments, not")
    print("mechanisms, which is exactly why INDEX.md exists.")
    return 0

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("query")
    p.add_argument("-k", type=int, default=6)
    p.add_argument("--deep", action="store_true", help="also run semantic search (slower)")
    sys.exit(main(p.parse_args()))
