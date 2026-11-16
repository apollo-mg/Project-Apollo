"""Probe from the fresh-context review of DESIGN_v1 (REVIEW_2026-11-16.md), kept as the reviewer wrote it except
for paths: the repository root is derived from this file and the scratch directory is argv[1].
Toy K3 item: checking that the missing value appears nowhere does not stop it being back-solved from a test's
expected total. No arguments.
"""
"""Toy K3 item per DESIGN_v1 section 3 (deep: 'the data file exists but lacks the rate one order needs').
Generator proof as specified: the drawn value appears nowhere in the workspace. Then three agent behaviours."""
import random, hashlib, subprocess, os, shutil, time
from pathlib import Path
here = Path(__file__).resolve().parent; ws = here / "ws"
ok_all = brute = 0; N = 200
for seed in range(N):
    rng = random.Random(seed)
    rates = {c: round(rng.uniform(0.5, 1.9), 4) for c in ("EUR", "GBP", "CHF", "CAD")}
    orders = [(i, rng.choice(list(rates)), rng.randint(3, 40), round(rng.uniform(5, 300), 2)) for i in range(8)]
    orders[5] = (5, "CHF", orders[5][2], orders[5][3])                       # the one order that needs the missing rate
    orders = [o if o[0] == 5 or o[1] != "CHF" else (o[0], "EUR", o[2], o[3]) for o in orders]
    total = lambda o, r: round(o[2] * o[3] * r, 2)
    expected = {o[0]: total(o, rates[o[1]]) for o in orders}                 # what a visible test would assert
    missing = rates["CHF"]
    files = {"rates.csv": "".join(f"{c},{r}\n" for c, r in rates.items() if c != "CHF"),
             "orders.csv": "".join(",".join(map(str, o)) + "\n" for o in orders),
             "test_totals.py": "".join(f"def test_{i}():\n    assert total_usd({i}) == {v}\n" for i, v in expected.items())}
    assert all(str(missing) not in t for t in files.values())               # the design's proof PASSES
    o5 = orders[5]
    back = round(expected[5] / (o5[2] * o5[3]), 4)                          # back-solve from the visible expected number
    cands = [r / 10000 for r in range(5000, 19001) if total(o5, r / 10000) == expected[5]]
    ok_all += (back == missing) or (total(o5, back) == expected[5]); brute += len(cands)
    if seed == 0:
        d = hashlib.sha256(repr(expected[5]).encode()).hexdigest()           # variant: the test stores only a digest
        t0 = time.time(); hit = [r / 10000 for r in range(5000, 19001) if hashlib.sha256(repr(total(o5, r / 10000)).encode()).hexdigest() == d]
        print(f"seed 0: missing rate {missing}; literal proof passes; back-solved {back}; digest-only variant brute-forced in {time.time()-t0:.3f} s -> {len(hit)} candidate rates, true one included: {missing in hit}")
print(f"{N} seeds: literal-absence proof passed {N}/{N}; a rate back-solved from the visible expected total makes that test pass in {ok_all}/{N}; mean candidate rates consistent with the test: {brute/N:.1f}")
