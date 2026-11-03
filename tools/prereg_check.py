#!/usr/bin/env python3
"""Does every pre-registration say what prior art it checked, and is "nothing found" true?

    tools/prereg_check.py data/receipts/foo/PREREG_BAR.md
    tools/prereg_check.py --staged            # preregs added or modified in the git index
    tools/prereg_check.py --all --summary     # counts only, over data/receipts/**/PREREG_*.md

WHY THIS EXISTS
---------------
CLAUDE.md requires a `**Prior art checked:**` line in every prereg, because the rule "grep INDEX.md
before designing anything" lived in a file nobody opened and indexed findings were re-derived
twice (2026-08-16, 2026-09-20), costing days. The prereg is written at the moment of need, so the
line rides on a ritual that already happens. But a rule in a document is still only a rule; this
makes it countable, and checks the one claim that can be checked mechanically: a line that says
"nothing found" while the repo's own index answers the same query.

It is a sense, not a gate: it speaks up only when the answer may already exist.

WHAT IT DOES, per prereg
------------------------
1. Finds the `**Prior art checked:**` field (also as a list item). Missing -> MISSING.
2. If the field claims nothing was found (and names no receipt, INDEX line or result file), it
   builds two queries -- the title, and the prereg's most distinctive terms (rarest in INDEX.md) --
   and runs tools/ledger_precheck.py on each, pointed at THIS checkout (its own ROOT is the local
   /mnt path). Its exit code decides, as everywhere else: 2 = prior art.
3. Hits are kept only if they could have been seen when the prereg was written: INDEX.md rows dated
   before the registration date, and receipt filenames first committed before it. FAILURE_MODES.md
   hits are dropped -- they catalogue how we err, not what we found. What survives is reported as
   PRIOR-ART?, with the top hits one line each.

Never `--deep`: that needs the local vector store, which cloud sessions and CI do not have.

Exit codes: 0 all pass, 1 a field is missing, 2 prior art may be unacknowledged (2 wins over 1).
"""
import argparse, contextlib, datetime, io, math, re, subprocess, sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RECEIPTS = REPO / "data" / "receipts"
INDEX = RECEIPTS / "INDEX.md"

FIELD = re.compile(r"^\s*(?:[-*]\s+)?\*\*Prior art checked:?\*\*:?", re.I)
NOTHING = re.compile(r"\b(nothing|no prior art|no hits|none found|no receipts?( found)?)\b", re.I)
# Anything that names a source means the author saw something and is scoping a claim, not denying prior art.
ACK = re.compile(r"(found:|prior art found|\.md\b|\bINDEX\b|\bL\d+\b|RESULT_|AFM-\d+|`[\w./-]+/`|\breceipts?\b|\bhits?\b|"
                 r"\bmatch(es)?\b|\bbaselines?\b|\babove\b)", re.I)
DATE = re.compile(r"\b(20\d\d)-(\d\d)-(\d\d)\b")
ROW_DATE = re.compile(r"\|\s*(\d\d)-(\d\d)\s*\|\s*$")
# Words every prereg uses; they say nothing about the topic.
GENERIC = {"pre-registration", "preregistration", "prereg", "registered", "before", "after", "any", "run", "runs",
           "row", "rows", "result", "results", "test", "tests", "file", "files", "each", "one", "two", "three",
           "not", "but", "than", "then", "same", "only", "also", "which", "will", "may", "more", "less", "per",
           "into", "over", "under", "between", "all", "both", "here", "there", "these", "those", "they", "their",
           "about", "versus", "does", "standard", "card", "abstend", "model", "models", "prediction", "predictions",
           "analysis", "data", "committed", "mark", "first", "new", "own", "prior", "art", "checked", "ledger_precheck.py",
           "nothing", "found", "receipts", "receipt", "what", "adds", "this", "where", "who", "whether", "still"}


def _lp():
    """tools/ledger_precheck.py as a module, re-pointed at this checkout (its ROOT is the desktop's /mnt path)."""
    sys.path.insert(0, str(REPO / "tools"))
    sys.dont_write_bytecode = True
    import ledger_precheck as lp
    lp.ROOT, lp.RECEIPTS = REPO, RECEIPTS
    lp.INDEX, lp.FAILMODES = INDEX, RECEIPTS / "FAILURE_MODES.md"
    return lp


def precheck(query):
    """Run ledger_precheck on `query` (no --deep). Returns (exit code, stdout). Tests stub this."""
    lp = _lp()
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        rc = lp.main(argparse.Namespace(query=query, k=50, deep=False))
    return rc, out.getvalue()


def rel(p):
    p = Path(p).resolve()
    return str(p.relative_to(REPO)) if p.is_relative_to(REPO) else p.name


def field(text):
    """The text of every Prior-art field, joined; None if there is none. A paragraph field runs to the next blank
    line, heading or bold lead-in; a list-item field also stops at the next item at the same or a shallower indent."""
    out, on, found, indent = [], False, False, 0
    for line in text.splitlines():
        if FIELD.match(line):
            found, on = True, True
            item = re.match(r"^(\s*)[-*]\s", line)
            indent = len(item.group(1)) if item else -1
            out.append(FIELD.sub("", line, count=1).strip()); continue
        if on:
            s = line.strip()
            m = re.match(r"^(\s*)[-*]\s", line)
            if (not s or s.startswith(("#", "**", "|")) or (m and (indent < 0 or len(m.group(1)) <= indent))):
                on = False
            else:
                out.append(s)
    return " ".join(out).strip() if found else None


def claims_nothing(f):
    """True when the field says nothing was found and names nothing it did find. "no receipts" is removed before the
    acknowledgement test, so the denial itself does not count as naming a receipt."""
    return bool(NOTHING.search(f)) and not ACK.search(NOTHING.sub("", f))


def registered(text):
    """The prereg's registration date: the first ISO date in it (all 155 on 2026-11-02 carry one)."""
    m = DATE.search(text)
    return datetime.date(*map(int, m.groups())) if m else None


def title(text):
    for line in text.splitlines():
        if line.startswith("# "):
            t = re.sub(r"^#\s*(pre-?registration|prereg)\b\s*[:\-—–]*\s*", "", line, flags=re.I)
            return t.strip(" -—–:")
    return ""


_LINES = None
_DF = {}
def df(w):
    """In how many INDEX.md lines `w` occurs as a whole word. ledger_precheck matches substrings ("port" hits "report"),
    which is the right recall for a person reading its output and too loose for a check that speaks up unasked; its
    exit code still gates every report here, and these filters only drop what it found."""
    global _LINES
    if _LINES is None:
        _LINES = [l.lower() for l in INDEX.read_text(errors="replace").splitlines()] if INDEX.exists() else []
    if w not in _DF:
        _DF[w] = sum(has(l, w) for l in _LINES)
    return _DF[w]


def has(low, w):
    """`w` as a whole word in lower-cased `low` ("unbound" is not in "unbounded")."""
    return re.search(rf"(?<![\w.-]){re.escape(w)}(?![\w-])", low) is not None


RARE = 12   # a term in more INDEX.md lines than this pairs with any other term and the hits become noise


def _rare(words):
    return [w for w in dict.fromkeys(words) if w not in GENERIC and not w.isdigit() and len(w) >= 4 and 0 < df(w) <= RARE]


def title_query(text, n=6):
    """The title, cut down to its terms that are rare in INDEX.md. The whole title has a dozen terms and
    ledger_precheck counts any line with two of them, so "P100" plus "llama.cpp" would be "prior art"."""
    return " ".join(_rare(_lp().terms(title(text)))[:n])


def distinctive(text, n=4):
    """The n terms that are frequent in the prereg and rare (but present) in INDEX.md."""
    tf = Counter(_lp().terms(text))
    scored = sorted(((tf[w] * math.log(600 / df(w)), w) for w in _rare(tf)), reverse=True)
    return " ".join(w for _, w in scored[:n])


def queries(text):
    """Up to two queries: the title's rare terms, and the prereg's most distinctive terms."""
    return list(dict.fromkeys(q for q in (title_query(text), distinctive(text)) if q))


def _added(path):
    """Date a receipt was first committed, or None (untracked / no git)."""
    r = subprocess.run(["git", "-C", str(REPO), "log", "--diff-filter=A", "--format=%as", "--", path],
                       capture_output=True, text=True)
    d = r.stdout.split()
    return datetime.date.fromisoformat(d[-1]) if r.returncode == 0 and d else None


def strong(body, words):
    """A row is evidence when it shares two query terms, one of them rare (in <= 4 INDEX lines), or a single very rare
    long one ("Ornith", "Kolibri").
    ledger_precheck also counts one term of 4+ letters for a one-word query, which on a title-derived query
    turns "curve" or "stage" into prior art."""
    low = body.lower()
    m = [w for w in words if has(low, w)]
    anchor = [w for w in m if df(w) <= 4]   # two common-ish words together ("high", "medium") are still noise
    return (len(m) >= 2 and bool(anchor)) or (len(m) == 1 and len(m[0]) >= 6 and df(m[0]) <= 3)


def hits(out, before, own, query=""):
    """Prior-art lines from ledger_precheck output that predate `before`: INDEX.md table rows and receipt filenames.
    ledger_precheck prints at most 300 chars of a line, which cuts off the date cell, so rows are re-read by number."""
    words = _lp().terms(query) if query else []
    rows = INDEX.read_text(errors="replace").splitlines() if INDEX.exists() else []
    keep, section = [], ""
    for line in out.splitlines():
        if line.startswith("=== "):
            section = line; continue
        s = line.strip()
        if not s or not line.startswith("  "):
            continue
        if "INDEX.md" in section:
            m = re.match(r"\[\d+ terms\] (L\d+): (.*)", s)
            if not m or not m.group(2).startswith("|") or m.group(2).startswith("| finding"):
                continue
            n = int(m.group(1)[1:])
            body = rows[n - 1].strip() if 0 < n <= len(rows) else m.group(2)
            if (own and own in body) or (words and not strong(body, words)):
                continue
            d = ROW_DATE.search(body)
            if before and d:
                try:
                    if datetime.date(before.year, int(d.group(1)), int(d.group(2))) >= before: continue
                except ValueError:
                    pass
            claim = re.sub(r"\*\*|`", "", body.strip("| ").split(" | ")[0])
            src = body.strip("| ").split(" | ")[1].strip("` ") if body.count(" | ") >= 1 else ""
            keep.append(f"INDEX.md {m.group(1)}: {claim[:110]}" + (f" -> {src}" if src else ""))
        elif "FILENAME" in section:
            if s == own or s.endswith("/" + Path(own or "?").name):
                continue
            # 2026-11-02: filename hits need a query term as a whole word too. ledger_precheck matches substrings, so the
            # Kolibri prereg's "ports" hit scale-gfx1201/drafts/SPECTRAL_REPORTS.md, an unrelated SCALE defect report.
            if words and not any(has(re.sub(r"[_/.]", " ", s.lower()), w) for w in words):
                continue
            d = _added(s)
            if before and (d is None or d >= before):
                continue
            keep.append(f"receipt {s}")
    return keep


def check(path):
    """('ok'|'missing'|'prior', lines to print)."""
    p = Path(path)
    text = p.read_text(errors="replace")
    name = rel(p)
    f = field(text)
    if f is None:
        return "missing", [f"MISSING   {name}: no **Prior art checked:** field"]
    if not claims_nothing(f):
        return "ok", [f"ok        {name}"]
    before = registered(text)
    for q in queries(text):
        rc, out = precheck(q)
        if rc != 2:
            continue
        found = hits(out, before, name, q)
        if found:
            lines = [f"PRIOR-ART? {name}: the field says nothing found; ledger_precheck \"{q}\" finds:"]
            lines += [f"    {h}" for h in found[:3]]
            return "prior", lines
    return "ok", [f"ok        {name} (nothing found, confirmed)"]


def staged():
    r = subprocess.run(["git", "-C", str(REPO), "diff", "--cached", "--name-only", "--diff-filter=AM"],
                       capture_output=True, text=True)
    return [REPO / l for l in r.stdout.splitlines() if re.fullmatch(r"PREREG_.*\.md", Path(l).name)]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--staged", action="store_true", help="preregs added or modified in the git index")
    ap.add_argument("--all", action="store_true", help="every data/receipts/**/PREREG_*.md")
    ap.add_argument("--summary", action="store_true", help="counts only")
    a = ap.parse_args(argv)
    paths = [Path(p) for p in a.paths]
    if a.staged: paths += staged()
    if a.all: paths += sorted(RECEIPTS.rglob("PREREG_*.md"))
    paths = list(dict.fromkeys(p.resolve() for p in paths))
    if not paths:
        if not (a.staged or a.all): ap.error("give PREREG_*.md paths, --staged or --all")
        return 0
    n = Counter()
    for p in paths:
        verdict, lines = check(p)
        n[verdict] += 1
        if not a.summary and not (verdict == "ok" and len(paths) > 1):
            print("\n".join(lines))
    if a.summary or len(paths) > 1:
        print(f"{len(paths)} preregs: {n['missing']} lack the prior-art field, "
              f"{n['prior']} may have unacknowledged prior art, {n['ok']} pass")
    return 2 if n["prior"] else 1 if n["missing"] else 0


if __name__ == "__main__":
    sys.exit(main())
