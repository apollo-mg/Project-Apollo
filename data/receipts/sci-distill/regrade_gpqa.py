#!/usr/bin/env python3
"""PREREG_SCI_DISTILL.md Deviation 1: grade GPQA replies with the registered rule AND a format-only fallback, from the
private rows (outside the repo), into a text-free file for the repo.
- registered (`correct`): the LAST "ANSWER: X" in the content (run_gpqa.py's rule).
- fallback (`correct_any`): if there is no such line, the LAST non-empty line of the content is a bare letter A-D,
  optionally wrapped in markdown or punctuation ("C", "**C**", "(C)", "C.", "\\boxed{C}"). Applied to both arms alike.
`answer_form` records which rule found the answer: "answer_line", "bare_letter" or "none".
Usage: regrade_gpqa.py PRIVATE_FILE PUBLIC_FILE OUT   (OUT = PUBLIC_FILE's rows plus correct_any and answer_form)"""
import json, re, sys
from run_gpqa import grade

BARE = re.compile(r"^[\s*_`$(\[]*(?:\\boxed\{\s*([A-D])\s*\}|([A-D]))[\s*_`$)\].:]*$")


def regrade(content, gold):
    got, ok = grade(content, gold)
    if got is not None:
        return ok, ok, "answer_line"
    lines = [l for l in (content or "").splitlines() if l.strip()]
    m = BARE.match(lines[-1]) if lines else None
    if m:
        letter = (m.group(1) or m.group(2)).upper()
        return False, letter == gold, "bare_letter"
    return False, False, "none"


def main():
    priv, pub, out = sys.argv[1:4]
    p = {(r["id"], r["round"]): r for r in map(json.loads, open(priv))}
    rows = [json.loads(l) for l in open(pub)]
    with open(out, "w") as f:
        f.write(json.dumps({**rows[0], "regraded": "Deviation 1: correct_any = registered rule or bare-letter fallback"}) + "\n")
        for r in rows[1:]:
            q = p[(r["id"], r["round"])]
            ok, ok_any, form = regrade(q["content"], q["gold"])
            assert ok == r["correct"], (r["id"], r["round"])   # the registered grade is reproduced exactly
            f.write(json.dumps({**r, "correct_any": ok_any, "answer_form": form}) + "\n")


if __name__ == "__main__":
    main()
