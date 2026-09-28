#!/usr/bin/env python3
"""Acceptance test for daydream_links.py closure evidence, from the first unattended brief (2026-09-28).

Four of that brief's five picks were already answered or shelved, and stage 2 had surfaced no evidence for them:
the answer sat further down the thread's own file (which stage 2 skipped), or only in a commit message. Each case
below is a real thread from that night. Anchors are found by CONTENT, not line number, and diary text is read at run
time (the diaries are local-only and never committed); a case whose file is absent prints SKIP.

Run: tools/test_daydream_links.py   (exit 0 when every case that could run passed)
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import daydream_links as L

ROOT = L.ROOT
results = []


def anchor(rel, needle):
    """(source 'file:line', paragraph text) for the first line containing needle, or None if the file is absent."""
    p = ROOT / rel
    if not p.exists():
        return None
    lines = p.read_text(errors="replace").splitlines()
    for n, l in enumerate(lines):
        if needle in l:
            para = [l.strip()]
            for m in range(n + 1, len(lines)):
                if not lines[m].strip() or lines[m].lstrip().startswith(("- ", "#")):
                    break
                para.append(lines[m].strip())
            return f"{rel}:{n + 1}", " ".join(para)
    raise AssertionError(f"anchor text not found in {rel}: {needle!r}")


def case(name, got, ok):
    results.append(ok)
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"\n       got: {got}"))


def skip(name):
    print("SKIP " + name + " (file absent)")


# 1. answered further down the same receipt (Limits poses it, an amendment section answers it)
a = anchor("data/receipts/loop-logits/RESULT_CROSS_MODEL.md", "Not shown: that Bonsai's stopping is intact overall")
hits = L.later_in_file(*a)
case("same-file answer: Amendment 1 result below the Limits line", [h["snippet"][:80] for h in hits],
     any("Amendment 1 result" in h["snippet"] for h in hits))

# 2. answered in a later part of the same day's diary
a = anchor("data/dev_diaries/2026-09-25_ledger.md", "144-gen run still in progress")
if a is None:
    skip("same-file answer: diary 'pending' closed by a later part")
else:
    hits = L.later_in_file(*a)
    case("same-file answer: diary 'pending' closed by a later part", [h["snippet"][:80] for h in hits],
         any("marker penalty: committed" in h["snippet"] for h in hits))

# 3. answered only in a commit message (af1a11c: endpointing off by default)
a = anchor("data/dev_diaries/2026-09-26_ledger.md", "endpointer")
if a is None:
    skip("commit answer: endpointer thread -> af1a11c")
else:
    got = L.Commits("2026-09-26", until="2026-09-28").candidates(a[1], "2026-09-26", set())
    case("commit answer: endpointer thread -> af1a11c", [c["source"] for c in got],
         any(c["source"].startswith("commit af1a11c") for c in got))

# 4. the commit that WROTE a question is excluded as its answer
a = anchor("data/receipts/loop-logits/RESULT_CROSS_MODEL.md", "Not shown: that Bonsai's stopping is intact overall")
own = L.own_line_commits(a[0])
case("own-commit exclusion: the file-creating commit f2f67b5", sorted(own), any(h.startswith("f2f67b5") for h in own))

# 5. negative: a thread that WAS still live that morning gets no same-file or commit evidence
# (the harvester matched this caveat in both files, so both files' own commits are excluded, as in the pipeline)
srcs = [anchor("data/receipts/quant-abstention/PREREG_CALIB.md", "Practical use needs a reference"),
        anchor("data/receipts/quant-abstention/RESULT_CALIB.md", "A user needs the Q8_0 reference rows")]
own = set().union(*(L.own_line_commits(s) for s, _ in srcs))
got = [h for s in srcs for h in L.later_in_file(*s)] + \
    L.Commits("2026-09-27", until="2026-09-28").candidates(srcs[0][1], "2026-09-27", own)
case("negative: Q8_0 reference-rows thread stays unanswered", [g["source"] for g in got], not got)

# 6. a resolution in a LATER CHUNK of another file counts (the file's first chunk is the original report)
a = anchor("data/receipts/vbr-artifact-store/RESULT_1C5E564B_ON_73.md", "still `clear()`s the whole")
_, closers = L.links_for(a[1], [a[0]], L.git_date(a[0].rpartition(":")[0]))
case("later chunk: INCIDENT 'fix landed upstream' update closes the stack-overflow thread",
     [c["source"] for c in closers], any("fix landed upstream" in c["snippet"] for c in closers))

# 7-8. the thread as harvested on 09-27, before its sentence was rewritten in place on the same day
old = "Whether the ranking holds *at the decision point in generation* is being measured (`PREREG_INCTX.md`)."
src = anchor("data/receipts/quant-abstention/RESULT_MAIN.md", "The decision-point readout was run")[0]
got = L.edited_in_place([src], old)
case("edited in place: the rewritten sentence ('readout was run') is shown as evidence",
     [g["snippet"][:90] for g in got], any("readout was run" in g["snippet"] for g in got))
got = L.prereg_results(old, [src])
case("prereg -> result: 'being measured (PREREG_INCTX.md)' finds RESULT_INCTX's H-ctx-rank line",
     [g["snippet"][:90] for g in got], any("RESULT_INCTX" in g["source"] and "H-ctx-rank" in g["snippet"] for g in got))
# the Q8_0 thread's wording is from PREREG_CALIB; its RESULT_CALIB source only paraphrases it (similarity match)
got = L.edited_in_place([s for s, _ in srcs], srcs[0][1])
case("negative: a sentence still present in one of its files is not 'edited'", got, not got)

# 9. BACKLOG rows led by FIXED are closed, not open items
bad = [b for b in L.backlog_items() if L.FIXED_ROW.match(b["text"])]
case("BACKLOG: no '**FIXED ...' row is listed as open", [b["id"] for b in bad], not bad)

print(f"{sum(results)}/{len(results)} passed")
sys.exit(0 if all(results) else 1)
