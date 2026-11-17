#!/usr/bin/env python3
"""Check the compendium's line rules (compendium/README.md, rules 1 and 2): every fact line carries a measured date
and at least one citation that exists (a repository path in backticks, or an AFM id found in FAILURE_MODES.md).
Lines under "Seen, not yet measured" are exempt. Exit 1 lists the lines that fail.
Usage: compendium_check.py [COMPENDIUM_DIR]"""
import re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATE = re.compile(r"\((?:measured|corrected|superseded)[^)]*20\d\d-\d\d-\d\d", re.S)
PATHS = re.compile(r"`([A-Za-z0-9_./-]+\.[A-Za-z0-9]+)`")


def facts(text):
    """(first line number, text) of each top-level bullet outside the exempt section; continuation lines are joined."""
    out, cur, exempt = [], None, False
    for n, line in enumerate(text.splitlines(), 1):
        if line.startswith("#"):
            exempt = "not yet measured" in line.lower()
            cur = None
        elif line.startswith("- "):
            cur = [n, line]
            if not exempt:
                out.append(cur)
        elif cur is not None and line.startswith("  "):
            cur[1] += "\n" + line
        else:
            cur = None
    return [(n, t) for n, t in out]


def check(directory, root=ROOT):
    afm = (root / "data" / "receipts" / "FAILURE_MODES.md")
    afm_ids = set(re.findall(r"AFM-\d+", afm.read_text())) if afm.exists() else set()
    bad = []
    for page in sorted(Path(directory).rglob("*.md")):
        if page.name == "README.md":
            continue
        for n, t in facts(page.read_text()):
            cites = [p for p in PATHS.findall(t) if (root / p).exists()] + [a for a in re.findall(r"AFM-\d+", t) if a in afm_ids]
            missing = [p for p in PATHS.findall(t) if "/" in p and not (root / p).exists()]
            if not DATE.search(t):
                bad.append((page, n, "no measured date"))
            if not cites:
                bad.append((page, n, "no citation that exists"))
            for p in missing:
                bad.append((page, n, f"cited path does not exist: {p}"))
    return bad


if __name__ == "__main__":
    d = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "compendium"
    bad = check(d)
    for page, n, why in bad:
        print(f"{page.relative_to(ROOT) if page.is_relative_to(ROOT) else page}:{n}: {why}")
    print(f"compendium: {'OK' if not bad else str(len(bad)) + ' problem(s)'}")
    sys.exit(1 if bad else 0)
