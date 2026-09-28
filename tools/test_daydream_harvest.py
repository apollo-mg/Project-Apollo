#!/usr/bin/env python3
"""Acceptance test for daydream_harvest.py: recall on an answer key of threads KNOWN to be open on 2026-09-27.

The key was written from the 2026-09-27 session before the harvester was first run. Each entry is a thread that a
human (or an agent reading the ledger by hand) would call open over the window 09-25..09-27, with a regex that any
faithful harvest line for it must match. The harvester sees only the files, never this key.

Run: tools/test_daydream_harvest.py [--days 3]   (exit 0 if recall >= 6/8)
The key covers 09-25..09-27; run later, pass --days to reach back to 09-25 (on 09-28: --days 4 -> 7/8).
"""
import argparse, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from daydream_harvest import recent_files, items

KEY = {
    "K1 split-state clear() / stack overflow unfixed":
        r"(split.state|clear\(\)|stack overflow).*(unchanged|not (re-)?tested|not fixed|untouched)|"
        r"(unchanged|not re-tested|untouched).*(split.state|clear\(\)|stack overflow)",
    "K2 speech-server first-start GGML_ASSERT flake": r"(startup|first start).*(GGML_ASSERT|flake)|not yet root-caused",
    "K3 CALIB stage 2 not run / re-scoped": r"stage 2.*(not run|re-scoped|go-ahead)|(not run|re-scoped).*stage 2",
    "K4 np4 store grew to 1.9 GB (worth watching)": r"1\.9 ?GB|worth watching",
    "K5 real Hermes subagent not tested": r"(real )?hermes subagent.*(not tested|was not tested)",
    "K6 daily driver switch to 1c5e564b is Mark's call": r"not switched to .?1c5e564b|mark's call",
    "K7 voice endpointer never confirmed firing": r"endpointer",
    # K8 was first written as r"decision point" and matched an unrelated loop-logits line (a false hit); tightened
    # after the first run, before the second, to require the in-generation readout being pending.
    "K8 ranking at the generation decision point pending": r"decision point in generation|in-context readout.*(open|measur|pending)",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=3)
    a = ap.parse_args()
    root = Path(__file__).resolve().parents[1]
    got = [(str(f.relative_to(root)), ln, t) for f in recent_files(root, a.days) for ln, t, *_ in items(f)]
    hits = 0
    for k, rx in KEY.items():
        m = next(((f, ln, t) for f, ln, t in got if re.search(rx, t, re.I)), None)
        hits += m is not None
        print(("HIT  " if m else "MISS ") + k + (f"\n       {m[0]}:{m[1]}  {m[2][:140]}" if m else ""))
    print(f"recall {hits}/{len(KEY)} over {len(got)} harvested items")
    sys.exit(0 if hits >= 6 else 1)


if __name__ == "__main__":
    main()
