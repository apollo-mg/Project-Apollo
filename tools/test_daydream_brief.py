#!/usr/bin/env python3
"""Tests for daydream_brief.py's mechanical filters, from the 2026-09-30 brief.

1. drop_resolved_adds: that brief proposed adding RESULT_CALIB.md:204's older wording to BACKLOG while listing its
   edited-in-place successor (a different thread id, same source line) as possibly closed.
2. split_suggested: commit-backed closure suggestions go to the one-line 'likely closed' list; diary- and
   receipt-backed ones stay in 'check'.
3. question_candidates / pending_question: the 2026-11-03 question asked about a switch BACKLOG had recorded as done;
   a thread whose commit id or file name is in settled BACKLOG evidence is no longer asked about.
Synthetic data only (BACKLOG text in a temp dir); no model calls. Run: tools/test_daydream_brief.py (exit 0 when all pass).
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

# 10-01: the resolved set must cover threads closed on EARLIER nights (absent from tonight's links)
every = dict(threads); every["closed_0930"] = {"text": NEW, "sources": ["data/receipts/quant-abstention/RESULT_CALIB.md:204"]}
check("an open sibling of a thread closed on an earlier night is shadowed (picks and adds)",
      B.shadowed({"thread": "old", **threads["old"]}, every, {"closed_0930"}))
check("an unrelated open thread is not shadowed", not B.shadowed({"thread": "oth", **threads["oth"]}, every, {"closed_0930"}))

verdicts = {"a": {"ev": {"source": "commit 9ed9296", "date": "2026-09-29"}},
            "b": {"ev": {"source": "data/dev_diaries/2026-09-29_ledger.md", "date": "2026-09-29"}},
            "c": {"ev": {"source": "data/receipts/x/RESULT_Y.md", "date": "2026-09-29"}},
            "d": {}}
likely, rest = B.split_suggested(["a", "b", "c", "d"], verdicts)
check("commit-backed suggestion -> likely", likely == ["a"])
check("diary, same-day receipt and missing evidence -> check", rest == ["b", "c", "d"])

# 2026-11-02: one question for Mark
import daydream_close as C
T = lambda m, first, kind="action", status="open", **kw: {"text": "x", "mentions": m, "first_seen": first, "kind": kind, "status": status, "sources": [], **kw}
st = {"threads": {"hot": T(4, "2026-10-01"), "new": T(1, "2026-11-01"), "scope": T(9, "2026-09-01", kind="scope"),
                  "old1": T(1, "2026-10-20"), "asked": T(9, "2026-09-01", asked_on="2026-10-30", question={"question": "q?"}),
                  "parked": T(9, "2026-09-01", status="parked", park_until="2026-11-02"),
                  "parkedlater": T(9, "2026-09-01", status="parked", park_until="2026-12-01")}}
cand = B.question_candidates(st, "2026-11-02")
check("candidates: a thread that keeps coming back ranks first", cand[0] == "hot")
check("candidates: one mention and one day old is not a candidate", "new" not in cand)
check("candidates: scope caveats and already-asked threads are excluded", "scope" not in cand and "asked" not in cand)
check("candidates: one mention but open for two weeks is a candidate", "old1" in cand)
check("pending: an asked, unanswered, open thread blocks a new question", B.pending_question(st) == "asked")
back = B.unpark(st, "2026-11-02")
check("unpark: a park that ends today comes back; a later one stays", back == ["parked"] and st["threads"]["parkedlater"]["status"] == "parked")
C.answer(st["threads"]["asked"], "drop", "not worth it", "2026-11-02", 30)
check("answer drop: closes the thread and clears the pending question",
      st["threads"]["asked"]["status"] == "closed" and B.pending_question(st) is None)
C.answer(st["threads"]["hot"], "park", "later", "2026-11-02", 30)
check("answer park: hidden until the date", st["threads"]["hot"]["status"] == "parked" and st["threads"]["hot"]["park_until"] == "2026-12-02")
C.answer(st["threads"]["old1"], "finish", "yes", "2026-11-02", 30)
check("answer finish: stays open and marked", st["threads"]["old1"]["status"] == "open" and st["threads"]["old1"]["answer"] == "finish")
check("answer finish: never asked about again", "old1" not in B.question_candidates(st, "2026-11-02"))

# 2026-11-03: never ask about what BACKLOG records as settled
import tempfile
BL = """# Backlog
| # | thread | cost | blocked by |
|---|---|---|---|
| ~~N2~~ | **DONE 10-02: `--resume` live on the daily driver (`resume-daily/NOTE_RESUME_DAILY_73.md`).** Was: ~~.73 daily driver to `1c5e564b`~~ **done via `510cbbbfa` (09-27)**; still open: a suspend/wake with `deadc0de9` | ~25 min | x |
| N9 | **Open:** port the fix in `abc1234f` to the P100 build (`RESULT_OPEN_PORT.md`) | ~1 h | x |
| N10 | Bisect the kv regression: ~~`5fd30894a` ruled out~~, `77eeaa1b2` still suspect (`RESULT_KV_BISECT.md`) | ~2 h | x |
- **FIXED in buun `0b2789f23` (09-25):** the abort. The daily driver is still on `feed1234a`; switching is Mark's call.
"""
SET = B.backlog_settled(BL)
TH = {"text": "x", "mentions": 3, "first_seen": "2026-10-01", "kind": "action", "status": "open", "sources": []}
mk = lambda text, **kw: {**TH, "text": text, **kw}
st2 = {"threads": {
    "drv": mk("The daily driver was not switched to 1c5e564b; that is Mark's call."),
    "port": mk("Port of abc1234f to the P100 build not yet run."),
    "inspan": mk("5fd30894a needs a second look on .194."),
    "outspan": mk("77eeaa1b2 is not root-caused yet."),
    "after_open": mk("Suspend/wake with deadc0de9 untested."),
    "after_open2": mk("Daily driver still on feed1234a, not switched yet."),
    "fixed": mk("The 0b2789f23 abort fix is not re-tested at -np 4."),
    "word": mk("The daily driver --resume is not tested across a suspend."),
}}
skipped = []
cand = B.question_candidates(st2, "2026-11-03", settled=SET, skipped=skipped)
sk = {x["id"]: x for x in skipped}
check("settled: the 1c5e564b thread is not asked (struck span in a struck-id DONE row)", "drv" not in cand and "drv" in sk)
check("settled: the skip records the anchor and the BACKLOG snippet",
      sk.get("drv", {}).get("anchors") == ["1c5e564"] and "1c5e564b" in sk["drv"]["backlog"][0]["snippet"]
      and sk["drv"]["backlog"][0]["kind"] == "struck")
check("open row: a thread whose anchor is only in an OPEN BACKLOG row is still asked", "port" in cand and "port" not in sk)
check("struck span in an open row: the anchor inside the span is settled", "inspan" not in cand and "inspan" in sk)
check("struck span in an open row: an anchor outside the span is not", "outspan" in cand)
check("done row: anchors after a 'still open' marker are not settled", "after_open" in cand)
check("FIXED bullet: anchors after 'still on' are not settled; before it they are", "after_open2" in cand and "fixed" not in cand)
check("shared words and backticked flags never skip (only commit ids and file names do)", "word" in cand)
st2["threads"]["drv"].update(asked_on="2026-11-03", asked_times=1, question={"question": "switch?"})
psk = []
check("pending: a settled asked question is not shown again; skip recorded",
      B.pending_question(st2, SET, psk) is None and [x["id"] for x in psk] == ["drv"])
check("pending: without settled evidence it is still pending", B.pending_question(st2) == "drv")
with tempfile.TemporaryDirectory() as d:
    none = B.load_backlog_settled(Path(d) / "BACKLOG.md")
    (Path(d) / "BACKLOG.md").write_text(BL)
    present = B.load_backlog_settled(Path(d) / "BACKLOG.md")
st2["threads"]["drv"].pop("asked_on")
sk0 = []
check("no BACKLOG file: no settled evidence, candidates unchanged",
      none == [] and B.question_candidates(st2, "2026-11-03", settled=none, skipped=sk0) == B.question_candidates(st2, "2026-11-03")
      and "drv" in B.question_candidates(st2, "2026-11-03") and sk0 == [])
check("BACKLOG file in a temp dir parses the same as the text", present == SET)

sys.exit(1 if fails else 0)
