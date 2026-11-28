# RESULT: the three machines can be trusted equally for scored results -- .194 and .73 are one instrument (byte-identical answers on the 9B and the 27B), the desktop changes wording on a third of answers but not the scores; and at the logit level the old P100s, not the 9070, sit furthest from the CPU reference

**Prereg:** `PREREG_STACK_DRIFT.md` (`325d4b74`) and Deviation 1 (the desktop on the ROCm 7.2.4 runtime: the system's 10.1
HIP runtime crashes, `NOTE_CACHYOS_HIP_BUG.md`). **Runs:** 2026-11-24, llama.cpp mainline `33aeb17f8` on all stacks:
desktop RX 9070 XT (built with ROCm 10.1, run on the 7.2.4 runtime), .194 P100 (NVIDIA 580.173.02, CUDA 12.4), .73 P100
(580.178.04, CUDA 12.4), desktop CPU as the reference. **Records:** M1 rows `quant-abstention/raw/main_DR*.jsonl`; logs,
KLD outputs and state in `raw/`. **Analysis:** `analyze_drift.py` -> `summary_drift.txt`, `RESULT_drift.json`.
**Launch failures (no rows lost):** on .73 the first 9B server ran out of memory (the daily model, killed a moment before,
had not released its VRAM) and the 27B did not load from .73's HDD within 8 minutes; both re-launched unchanged except for
waiting on free VRAM and a 40-minute load window (`rerun_n73.sh`).

## M1 (Qwen3.5-9B Q8_0 twice per stack; Qwen3.8-27B Q8_0 once per P100 node; greedy, thinking off)

| stack | invented declined | hard right | easy right |
|---|---|---|---|
| desktop (both runs) | 64 | 42 | 34 / 40 |
| .194 (both runs) | 66 | 44 | 34 / 40 |
| .73 (both runs) | 66 | 44 | 34 / 40 |
| 27B on .194 / on .73 | 59 / 59 | 48 / 48 | 33 / 33 |

| prediction | result |
|---|---|
| D1 each machine agrees with itself, 240/240 (0.85) | **holds:** 240, 240, 240 |
| D2 the two P100 machines identical, 240/240 (0.75) | **holds:** 240 of 240, every pairing of their four runs, despite different driver versions |
| D3 the desktop drifts in wording, not results (0.9 / 0.7 / 0.7) | **holds:** 153 of 240 answers identical to the P100s; 230 of 240 grades the same; invented declined -0.02 [-0.07, +0.03], hard right -0.02 [-0.05, +0.00] |
| D4 every GPU stack within KLD 0.005 of the CPU, top token >= 98 % (0.7) | **fails on the P100s:** desktop 0.00067 and 98.8 %; .194 and .73 0.0065 and 94.6 % (identical to each other) |
| D5 the 27B identical on .194 and .73 (0.7) | **holds:** 240 of 240 |

Perplexity on the same 10 chunks: CPU 9.2096, desktop 9.2195 (+0.11 %), P100s 9.2401 (+0.33 %).

## Reading

1. **For scored results the three machines are interchangeable.** Wording changes between the desktop and the P100s on
   87 of 240 answers, the grade on 10, and the totals by 2 items or fewer -- inside every interval.
2. **.194 and .73 are one instrument.** Same answers, and KLD statistics identical to every printed digit, on the 9B and on the 27B, with
   different NVIDIA driver versions. A run on either can replace a run on the other, byte for byte.
3. **Replays must stay on one machine family.** A replay that crosses from the desktop to a P100 will differ in wording
   for a third of the answers; that is drift, not a fault.
4. **The P100s sit furthest from the CPU reference, not the 9070.** Against the CPU reference the desktop's next-token distributions are
   ten times closer than the P100s' (mean KLD 0.00067 vs 0.0065), and pick the same top token 98.8 % of the time against
   94.6 %. A plausible cause is the lower-precision paths llama.cpp takes on sm_60 (no `dp4a`), untested here. The effect
   on scores is still small (D3).

## Limits

One commit, one quant (Q8_0), greedy only, one 9B and one 27B; the desktop ran on the 7.2.4 runtime with 10.1-built
binaries (Deviation 1); KLD over 10 chunks; the CPU is a reference, not ground truth.

## Follow-up (2026-11-27): the P100 gap explained (`RESULT_SM60_FP32.md`)

The untested cause in reading 3 was mainline's fast-FP16 path on sm_60. With the three-line carve-out, the same KLD run on
.73 falls from 0.006451 to 0.000603 (same top 99.06 %), level with the desktop. M1 wording against the desktop does not
improve (154 vs 153 of 240 identical), so the D3 drift is greedy decoding on different numeric paths, not this bug.
