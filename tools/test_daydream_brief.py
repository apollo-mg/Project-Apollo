#!/usr/bin/env python3
"""Tests for daydream_brief.py's mechanical filters, from the 2026-09-30 brief.

1. drop_resolved_adds: that brief proposed adding RESULT_CALIB.md:204's older wording to BACKLOG while listing its
   edited-in-place successor (a different thread id, same source line) as possibly closed.
2. split_suggested: commit-backed closure suggestions go to the one-line 'likely closed' list; diary- and
   receipt-backed ones stay in 'check'.
Synthetic data only; no files or model calls. Run: tools/test_daydream_brief.py (exit 0 when all pass).
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import daydream_brief as B

fails = []


def check(name, cond):
    print(("PASS  " if cond else "FAIL  ") + name)
    if not cond:
        fails.append(name)


OLD = ("**Practical use needs a reference.** `b` is fitted against Q8_0's readout on these 240 items. A user calibrating "
       "their own file needs the Q8_0 reference rows (which could ship with the corpus) or labelled items.")
NEW = ("`b` is fitted against Q8_0's readout on these 240 items. A user needs the Q8_0 reference rows or labelled items "
       "to calibrate a file. **Shipped 2026-09-28:** `calibrate.py`.")
OTHER = "First start after another GPU job hits `GGML_ASSERT`; second start works. Two of four restarts today."
threads = {
    "old": {"text": OLD, "sources": ["data/receipts/quant-abstention/RESULT_CALIB.md:204"]},
    "new": {"text": NEW, "sources": ["data/receipts/quant-abstention/RESULT_CALIB.md:204"]},
    "oth": {"text": OTHER, "sources": ["data/dev_diaries/2026-09-26_ledger.md:104"]},
    "far": {"text": NEW, "sources": ["data/receipts/elsewhere/RESULT_X.md:9"]},
}
adds = [{"thread": k, "text": threads[k]["text"], "sources": threads[k]["sources"]} for k in ("old", "oth")]

kept = [c["thread"] for c in B.drop_resolved_adds(adds, threads, resolved={"new"})]
check("edited-in-place sibling of a suggested closure is dropped (same source line)", "old" not in kept)
check("an unrelated open thread is kept", "oth" in kept)

threads_nd = {k: v for k, v in threads.items() if k != "new"}
kept2 = [c["thread"] for c in B.drop_resolved_adds(adds, threads_nd, resolved={"far"})]
check("near-duplicate text of a resolved thread is dropped even from another file", "old" not in kept2)
check("near-duplicate rule leaves unrelated text alone", "oth" in kept2)
check("nothing resolved -> nothing dropped", [c["thread"] for c in B.drop_resolved_adds(adds, threads, set())] == ["old", "oth"])
check("near_dup is not fooled by one shared word", not B.near_dup("the store grew too large", "the server survived the store"))

verdicts = {"a": {"ev": {"source": "commit 9ed9296", "date": "2026-09-29"}},
            "b": {"ev": {"source": "data/dev_diaries/2026-09-29_ledger.md", "date": "2026-09-29"}},
            "c": {"ev": {"source": "data/receipts/x/RESULT_Y.md", "date": "2026-09-29"}},
            "d": {}}
likely, rest = B.split_suggested(["a", "b", "c", "d"], verdicts)
check("commit-backed suggestion -> likely", likely == ["a"])
check("diary, same-day receipt and missing evidence -> check", rest == ["b", "c", "d"])

sys.exit(1 if fails else 0)
