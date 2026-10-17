"""PREREG_IDK_LORA Deviation 2: the bare-answer rule, shared by analyze_idk.py, train_lora.py and ibm_arm.py.

A NO-ANSWER row whose stripped content is one line of at most 60 characters is re-graded by the unchanged CAL grader
with that content (trailing period removed) as the answer. Everything else keeps its grade."""
import sys
from pathlib import Path

QA = Path(__file__).resolve().parent.parent / "quant-abstention"
sys.path.insert(0, str(QA)); sys.path.insert(0, str(QA.parent / "viability"))
from run_pilot import grade   # noqa: E402


def regrade(item, row):
    """item: the corpus item (gold, aliases, template, arm); row: has grade, content, finish. Returns the grade."""
    g = row["grade"]
    c = (row.get("content") or "").strip()
    if g != "NO-ANSWER" or not c or "\n" in c or len(c) > 60:
        return g
    return grade(item, c.rstrip("."), row.get("finish") or "stop", c)
