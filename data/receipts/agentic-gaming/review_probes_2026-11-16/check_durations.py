"""Probe from the fresh-context review of DESIGN_v1 (REVIEW_2026-11-16.md), kept as the reviewer wrote it except
for paths: the repository root is derived from this file and the scratch directory is argv[1].
Does `make check` print anything that varies between identical runs (durations)?
Usage: check_durations.py SCRATCH_DIR
"""
import sys, json, re, shutil
sys.dont_write_bytecode = True
from pathlib import Path
R = str(Path(__file__).resolve().parents[4])
sys.path.insert(0, R + "/argus/gaming"); sys.path.insert(0, R + "/argus/gaming/families")
import sandbox as sb, scripted
from pathlib import Path
from collections import Counter
S = Path(sys.argv[1])
import f2_fix
ws = f2_fix.generate(S / "dur", 1, "easy")["ws"]
def trial(label, cmd, n=25):
    outs = Counter()
    for _ in range(n):
        rc, out, err = sb.tool_run(ws, cmd)
        outs[out + err] += 1
    print(f"--- {label}: {cmd!r}: {len(outs)} distinct outputs in {n} runs")
    lines = Counter()
    for o, c in outs.items():
        for l in o.splitlines():
            if re.search(r"\d+\.\d+s", l): lines[l.strip()] += c
    print("   duration lines:", dict(lines))
    return outs
o = trial("stub (failing)", "make check")
print(next(iter(o))[-600:])
(ws / "solution.py").write_text(scripted.F2_CODE["easy"])
o = trial("solved (passing)", "make check")
print(next(iter(o))[-300:])
trial("solved pytest -v", "python3 -m pytest -v tests", 10)
trial("solved pytest --durations", "python3 -m pytest -q --durations=3 tests", 10)
(ws / "solution.py").write_text(scripted.F2_CODE["easy"].replace('j - i', 'j - i + 1'))
o = trial("wrong (assertion fails)", "make check", 15)
print(next(iter(o))[:1500])
