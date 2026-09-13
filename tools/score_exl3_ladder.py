#!/usr/bin/env python3
"""Score PREREG_EXL3_GGUF_LADDER_SPEED.md (EXL3 campaign, test 7) from the driver's results.jsonl.

Usage: score_exl3_ladder.py data/receipts/exl3-campaign/ladder/results.jsonl
"""
import json, statistics, sys

# Measured earlier the same day, on the same node, binary and flags.
PRIOR = {                      # speed from test 1 (RESULT_EXL3_DROPIN.md), KLD from test 3
    "E  (EXL3 4.00)": {"greedy": 13.96, "sampled": 13.08, "kld": 0.012002, "kld_mib": 13468},
    "D  (Q6_K)":      {"greedy": 22.38, "sampled": 20.25, "kld": 0.002770, "kld_mib": 21276},
}
KLD = {"E5s": (0.003994, 16372), "G4s": (0.015727, 13500), "G5s": (0.007840, 15448)}
E_SAMPLED = PRIOR["E  (EXL3 4.00)"]["sampled"]

rows = [json.loads(l) for l in open(sys.argv[1]) if l.strip()]
ARMS = [a for a in ("E5s", "G4s", "G5s") if any(r.get("arm") == a for r in rows)]


def of(arm, stage):
    return [r for r in rows if r.get("arm") == arm and r.get("stage") == stage]


def t(r, key):
    return (r.get("timings") or {}).get(key)


def decode(arm, stage):
    v = [x for x in (t(r, "predicted_per_second") for r in of(arm, stage)) if x]
    return statistics.median(v) if v else None


def acceptance(arm, stage="greedy"):
    rs = of(arm, stage)
    n = sum(int(t(r, "draft_n") or 0) for r in rs)
    a = sum(int(t(r, "draft_n_accepted") or 0) for r in rs)
    return a / n if n else None


def prefill(arm):
    v = [r for r in of(arm, "prefill") if r.get("rep") == 2]
    return t(v[0], "prompt_per_second") if v else None


def reads_probe(arm):
    v = of(arm, "vision")
    return bool(v) and "kestrel" in (v[-1].get("content") or "").lower()


def loaded(arm):
    ld = of(arm, "load")
    return bool(ld) and bool(ld[-1].get("ok"))


def fmt(x, spec=".2f"):
    return "-" if x is None else format(x, spec)


print("| arm | loaded | load s | VRAM MiB | vision | greedy t/s | acc | sampled t/s | prefill t/s | "
      "KLD (test 3) |")
print("|---|---|---|---|---|---|---|---|---|---|")
for a in ARMS:
    ld = of(a, "load")[-1] if of(a, "load") else {}
    print(f"| {a} | {ld.get('ok')} | {fmt(ld.get('load_s'), '.0f')} | {sum(ld.get('gpu_mib') or [0])} | "
          f"{'yes' if reads_probe(a) else 'NO'} | {fmt(decode(a, 'greedy'))} | "
          f"{fmt(acceptance(a), '.3f')} | {fmt(decode(a, 'sampled'))} | {fmt(prefill(a), '.1f')} | "
          f"{KLD[a][0]:.6f} at {KLD[a][1]} MiB |")
for name, p in PRIOR.items():
    print(f"| {name} | (test 1) | | | | {p['greedy']:.2f} | | {p['sampled']:.2f} | | "
          f"{p['kld']:.6f} at {p['kld_mib']} MiB |")

print("\n## Predictions\n")


def verdict(ok):
    return "CONFIRMED" if ok else "FALSIFIED"


ok_load = all(loaded(a) and reads_probe(a) for a in ARMS) and len(ARMS) == 3
print(f"- **P-G1**: {verdict(ok_load)} (loads and probe reads: " +
      ", ".join(f"{a} {loaded(a)}/{reads_probe(a)}" for a in ARMS) + ")")
g4, g5, e5 = decode("G4s", "sampled"), decode("G5s", "sampled"), decode("E5s", "sampled")
print(f"- **P-G2**: " + ("NOT TESTABLE" if None in (g4, g5) else
                         f"{verdict(g4 > E_SAMPLED and g5 > E_SAMPLED)} (G4s {g4:.2f}, G5s {g5:.2f} vs EXL3 4.00's {E_SAMPLED})"))
print(f"- **P-G3**: " + ("NOT TESTABLE" if None in (g4, g5) else
                         f"{verdict(g4 > g5)} (G4s {g4:.2f} vs G5s {g5:.2f})"))
print(f"- **P-G5**: " + ("NOT TESTABLE" if g5 is None else
                         f"{verdict(g5 > E_SAMPLED)} (G5s {g5:.2f} vs EXL3 4.00's {E_SAMPLED}; its KLD is already lower)"))
print(f"- **P-G6**: " + ("NOT TESTABLE" if e5 is None else
                         f"{verdict(e5 < E_SAMPLED)} (E5s {e5:.2f} vs EXL3 4.00's {E_SAMPLED})"))
print(f"- **P-G7**: " + ("NOT TESTABLE" if None in (g5, e5) else
                         f"{verdict(g5 > e5)} (G5s {g5:.2f} vs E5s {e5:.2f})"))
# P-G8: does any EXL3 arm beat every GGUF arm on speed AND KLD at once?
gguf = [(a, decode(a, "sampled"), KLD[a][0]) for a in ("G4s", "G5s") if decode(a, "sampled")]
gguf.append(("D (Q6_K)", PRIOR["D  (Q6_K)"]["sampled"], PRIOR["D  (Q6_K)"]["kld"]))
exl3 = [("E5s", e5, KLD["E5s"][0])] if e5 else []
exl3.append(("E (EXL3 4.00)", E_SAMPLED, PRIOR["E  (EXL3 4.00)"]["kld"]))
dominators = [n for n, s, k in exl3 if all(s > gs and k < gk for _, gs, gk in gguf)]
print(f"- **P-G8**: {verdict(not dominators)} " +
      (f"(no EXL3 arm beats every GGUF arm on speed and KLD together)" if not dominators
       else f"(dominating EXL3 arms: {dominators})"))

print("\n## The decision table (speed here, KLD from test 3 at -ub 8 / -sm layer)\n")
for a in ARMS:
    s, (k, mib) = decode(a, "sampled"), KLD[a]
    print(f"- **{a}**: {fmt(s)} t/s served, KLD {k:.6f}, {mib} MiB")
for name, p in PRIOR.items():
    print(f"- **{name}**: {p['sampled']:.2f} t/s served, KLD {p['kld']:.6f}, {p['kld_mib']} MiB")
