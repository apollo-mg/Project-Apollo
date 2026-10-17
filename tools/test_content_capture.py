#!/usr/bin/env python3
"""Tests for content_capture.py and content_digest.py's mechanical guards (2026-10-17).

1. Privacy: a deny-listed line never reaches the model, and a candidate that still matches is dropped.
2. Grounding: numbers, the quote and evidence must appear in the input; prose numbers that don't are flagged.
3. Chunking: a long window is split, not truncated, and ids stay unique across chunks.
4. Digest validation: unknown and duplicate ids are dropped, and a capture the model left out becomes its own topic.
Synthetic data only; the model is a stub and output goes to a temp dir. Run: tools/test_content_capture.py (exit 0 when
all pass).
"""
import json, re, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import content_capture as C
import content_digest as D

fails = []


def check(name, cond):
    print(("PASS  " if cond else "FAIL  ") + name)
    if not cond:
        fails.append(name)


tmp = Path(tempfile.mkdtemp())
(tmp / "terms.txt").write_text("# test list\nZorblax\nre:(?i)\\bsecretproj\\w*\n")
deny = C.load_deny(str(tmp / "terms.txt"))

events = ["HUMAN  Wow, the 2-bit file refuses only 16 of 100 invented questions, the parent 92.",
          "SAY    Plain 2-bit refuses 44; see RESULT_BOLT_SPLIT.md.",
          "HUMAN  Also my call with Zorblax went fine.",
          "SAY    The SecretProject kernels are private.",
          "TOOL   Bash  command=ls",
          "ERR    [NONZERO] Bash(grep x): Exit code 1",
          "ERR    [FAIL] Bash(hf download): Error: file over 50 GB needs hf_xet",
          "HUMAN  reach me at someone@example.com"]
lines, n_denied = C.window_lines(events, deny)
text = "\n".join(lines)
check("deny-listed and built-in-pattern lines are removed before the model", n_denied == 3
      and "Zorblax" not in text and "SecretProject" not in text and "example.com" not in text)
check("TOOL and NONZERO lines are dropped, FAIL kept", "TOOL" not in text and "[NONZERO]" not in text and "[FAIL]" in text)

seen_prompts = []
def stub(items):
    def f(host, prompt, timeout=900):
        seen_prompts.append(prompt); return {"items": items}
    return f

good = {"title": "QAD cost refusals", "kind": "finding", "hook": "A 2-bit file refused 16 of 100 fakes, not 92.",
        "context": "Comparing files.", "numbers": ["16 of 100", "92", "0.31"], "quote": "Wow, the 2-bit file refuses only",
        "evidence": ["RESULT_BOLT_SPLIT.md", "RESULT_INVENTED.md"], "audience": 5}
leaky = dict(good, title="Zorblax kernels", numbers=[], quote="", evidence=[])
prose = dict(good, title="Prose number", hook="It was 3.7x faster.", numbers=[], quote="", evidence=[])
C.call_model = stub([good, leaky, prose])
out = tmp / "cand.jsonl"
res = C.capture(events, "http://stub", "", "2026-10-17 15:05", "test", deny, str(out))
rows = [json.loads(x) for x in out.read_text().splitlines()]
check("prompt carries no denied text", all("Zorblax" not in p for p in seen_prompts))
check("a candidate matching the deny list is dropped", res["dropped_private"] == 1 and len(rows) == 2)
g = rows[0]
check("numbers not in the input are removed", g["numbers"] == ["16 of 100", "92"])
check("a quote from HUMAN text is kept", g["quote"] == "Wow, the 2-bit file refuses only")
check("evidence not in the input is removed", g["evidence"] == ["RESULT_BOLT_SPLIT.md"])
check("prose numbers absent from the input are flagged", rows[1]["ungrounded_numbers"] == ["3.7"])
check("removed count is reported", res["removed_ungrounded"] == 2)

bad_quote = dict(good, quote="I never said this", numbers=[], evidence=[])
C.call_model = stub([bad_quote])
out2 = tmp / "cand2.jsonl"
C.capture(events, "http://stub", "", "2026-10-17 16:05", "test", deny, str(out2))
check("a quote not in HUMAN text is blanked", json.loads(out2.read_text())["quote"] == "")

long_events = [f"HUMAN  line {i} " + "x" * 2000 for i in range(60)]
parts = C.chunks(C.window_lines(long_events, deny)[0], max_chars=45000, max_chunks=12)
check("a 120k-char window is split into 3 chunks, nothing dropped", len(parts) == 3 and sum(map(len, parts)) == 60)
C.call_model = stub([dict(good, numbers=[], quote="", evidence=[])])
out3 = tmp / "cand3.jsonl"
r3 = C.capture(long_events, "http://stub", "", "2026-10-17 17:05", "test", deny, str(out3), max_chunks=12)
ids = [json.loads(x)["id"] for x in out3.read_text().splitlines()]
check("ids are unique across chunks", r3["chunks"] == 3 and len(ids) == 3 and len(set(ids)) == 3)

cap = [{"id": i, "title": i, "hook": "h", "window": "2026-10-1%d 10:00" % n, "kind": "finding", "context": "c",
        "numbers": [], "quote": "", "evidence": [], "audience": 3} for n, i in enumerate(["a", "b", "c"], 1)]
topics = D.validate([{"title": "T1", "hook": "h", "ids": ["a", "zz", "a"], "talking_points": [], "status": "ready"},
                     {"title": "T2", "hook": "h", "ids": ["a"], "talking_points": [], "status": "weak"},
                     {"title": "T3", "hook": "h", "ids": ["b"], "talking_points": [], "status": "developing"}], cap)
check("digest: unknown/duplicate ids dropped, empty topics removed",
      [t["ids"] for t in topics[:2]] == [["a"], ["b"]] and topics[0]["title"] == "T1")
check("digest: a capture the model left out becomes its own topic", topics[-1]["ids"] == ["c"] and topics[-1]["unmerged"])
sheet = D.render(topics, cap, "ok", D.datetime(2026, 10, 17), 7)
check("sheet labels model text", "Hook (model):" in sheet and "model-written" in sheet)

sys.exit(1 if fails else 0)
