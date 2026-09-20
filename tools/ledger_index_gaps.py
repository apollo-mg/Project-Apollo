#!/usr/bin/env python3
"""Which receipts are missing from data/receipts/INDEX.md?

    ./tools/ledger_index_gaps.py            # summary + the 20 most recent gaps
    ./tools/ledger_index_gaps.py --all      # every gap
    ./tools/ledger_index_gaps.py --quiet    # one line, for ledger_health.sh

WHY THIS EXISTS
---------------
INDEX.md is the mechanism-keyed lookup that stops work being re-derived. Its rule is "when a
receipt lands, add a line here." Nothing enforces that, so on 2026-09-20 the newest indexed entry
was 09-12 while 214 receipts had been modified since -- and a session re-derived a finding the
index had held since July.

An index that is 8 days stale is worse than one that is empty, because it is consulted and
trusted. This makes the staleness visible.

Not every receipt belongs in the index: it is keyed by MECHANISM, and raw data, predictions and
partials are noise there. Those are filtered below, so the count stays actionable rather than
alarming.
"""
import argparse, re, sys
from pathlib import Path
from datetime import datetime

ROOT = Path("/mnt/TG_2TB/Projects/Apollo")
INDEX = ROOT / "data/receipts/INDEX.md"
RECEIPTS = ROOT / "data/receipts"

# Receipts that carry a MECHANISM finding. Predictions, raw dumps, partials and state files do
# not belong in a mechanism index; counting them would make the gap list unactionable.
WORTH = re.compile(r"^(RESULT|FINDING|NOTE|ANALYSIS|INCIDENT|METHOD)_", re.I)
SKIP_DIRS = {"raw", "logs", "state", "runs"}

def indexed_names(text):
    """Any receipt path mentioned anywhere in INDEX.md counts as indexed."""
    return {Path(m).name for m in re.findall(r"[A-Za-z0-9_./-]+\.md", text)}

def main(a):
    if not INDEX.exists():
        print("INDEX.md missing", file=sys.stderr); return 1
    have = indexed_names(INDEX.read_text(errors="replace"))
    gaps = []
    for p in RECEIPTS.rglob("*.md"):
        if p.name == "INDEX.md" or set(p.relative_to(RECEIPTS).parts[:-1]) & SKIP_DIRS:
            continue
        if not WORTH.match(p.name):
            continue
        if p.name not in have:
            gaps.append((p.stat().st_mtime, p.relative_to(ROOT)))
    gaps.sort(reverse=True)

    newest_indexed = max(re.findall(r"\|\s*(\d{2}-\d{2})\s*\|", INDEX.read_text(errors="replace")) or ["??-??"])
    if a.quiet:
        if gaps:
            print(f"index: {len(gaps)} mechanism receipts not in INDEX.md "
                  f"(newest indexed entry {newest_indexed}); run tools/ledger_index_gaps.py")
        else:
            print("index: complete")
        return 2 if gaps else 0

    print(f"INDEX.md newest dated entry: {newest_indexed}")
    print(f"mechanism receipts not indexed: {len(gaps)}\n")
    show = gaps if a.all else gaps[:20]
    for mt, rel in show:
        print(f"  {datetime.fromtimestamp(mt):%Y-%m-%d}  {rel}")
    if not a.all and len(gaps) > len(show):
        print(f"\n  ... and {len(gaps)-len(show)} more (--all)")
    if gaps:
        print("\nAdd one line each to data/receipts/INDEX.md: the MECHANISM tags someone would")
        print("search for, and the claim in a checkable form. An index nobody updates is worse")
        print("than none, because it is still trusted.")
    return 2 if gaps else 0

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--all", action="store_true")
    p.add_argument("--quiet", action="store_true")
    sys.exit(main(p.parse_args()))
