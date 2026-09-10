#!/usr/bin/env python3
"""Is the most recent diary section actually a usable diary entry?

WHY THIS EXISTS: an audit on 2026-08-30 found that 8 of 18 sections written since the ledger
launched were unusable -- six were degenerate `////////` runs, two were the model's raw
reasoning -- and EVERY ONE of those runs reported status=ok. Both observers checked liveness;
neither looked at the artifact. The heartbeat is not the product.

Exit 0 = looks like an entry. Exit 1 = prints a one-line reason.
"""
import re, sys, os, collections

def classify(body):
    b = body.strip()
    # Callers disagree about whether the "## HH:MM — N events" header is part of the body:
    # ledger_run.sh strips it, ledger_index.py does not. Left unhandled, the first-line checks
    # below silently test the HEADER and can never fire -- which is how a raw-reasoning section
    # got indexed even after this checker existed. Normalise here, once.
    b = re.sub(r"\A##\s[^\n]*\n", "", b).strip()
    if not b:
        return "entry is empty"
    if b.startswith("_(model unavailable"):
        return None                      # honest skeleton fallback, not a defect
    if "think>" in b:
        return "contains chain-of-thought tags — reasoning leaked into the diary"

    # Degenerate repetition. The `////` failure mode is fluent-looking garbage: one character
    # dominating. Measured on non-whitespace so indentation cannot mask it.
    ns = re.sub(r"\s", "", b)
    if ns:
        ch, n = collections.Counter(ns).most_common(1)[0]
        if not ch.isalnum() and n / len(ns) > 0.40:
            return f"degenerate output — {n/len(ns):.0%} of the entry is the character {ch!r}"

    first = next((l for l in b.split("\n") if l.strip()), "")
    # Untagged reasoning: the model planning out loud instead of writing the entry. Happens when
    # max_tokens runs out mid-thought, so no closing tag ever appears and stripping cannot help.
    if re.match(r"(Let me |Let's |I need to |I'll |I should |Now let me |First,? I )", first):
        return f"starts with planning language (\"{first[:48]}...\") — untagged reasoning"
    # Starting mid-sentence means the beginning was cut off: lowercase word, closing punctuation,
    # or a code span opened with nothing before it.
    if re.match(r"[a-z]|[,;:.)]|`\s", first):
        return f"starts mid-sentence (\"{first[:48]}...\") — likely a truncated block"
    return None

def main(argv):
    import datetime
    root = "/mnt/TG_2TB/Projects/Apollo"
    path = argv[1] if len(argv) > 1 else \
        f"{root}/data/dev_diaries/{datetime.datetime.now():%Y-%m-%d}_ledger.md"
    if not os.path.exists(path):
        return 0                          # absence is a staleness question, not a validity one
    secs = re.split(r"^## ", open(path, errors="replace").read(), flags=re.M)[1:]
    if not secs:
        return 0
    body = "\n".join(secs[-1].split("<details>")[0].split("\n")[1:])
    reason = classify(body)
    if reason:
        print(reason)
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv))
