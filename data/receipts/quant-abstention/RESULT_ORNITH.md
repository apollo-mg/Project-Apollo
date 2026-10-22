# Result -- Ornith-1.5-122B (Q3) joins the honest group: hard 0.77, refuses 85 of 100 invented questions; between Flash-Next and Super VL, far above the small-active models; all four predictions hold

**Prereg:** `PREREG_ORNITH.md` (`1a74f197`, before any Ornith row). **Analysis:** `analyze_ornith.py` -> `RESULT_ornith.json`.
**Raw:** `raw/main_ORN.jsonl` (240 rows, `--usage`), `raw/ornith_state.log`.

**Run (2026-10-22 16:49 -> 17:18):** Unsloth `UD-Q3_K_XL` (3 shards, sha256 verified), .194 4x P100 150 W, llama.cpp
`c7fc509`, `-ngl 99 -sm layer -c 8192 -ctk f16 -ctv f16 -np 1 -fit off -ts 15,12,11,10`, all layers on GPU (14.8 / 15.5
/ 14.6 / 11.1 GB). Thinking off by the template's own switch; render check and R-slot on (the 27B's path). Smoke gate
passed ("323", no reasoning). 4.4 s per answer, 21.5 tok/s decode, no answer unfinished.

**Placement and staging notes (recorded in the state log before the arm):**
- `/dev/shm` on .194 is `usrquota`: the download died at 48.6 GiB ("Disk quota exceeded", first read as a network
  error). Shard 3 was copied to disk (sha256 verified) and symlinked into the shard directory.
- An even layer split put 17.9 GB on a 17.2 GB card: this quant's layers 23-47 are ~1.4 GB vs ~1.0 GB before. A
  byte-balanced `-ts 15,12,11,10` loads with every layer on the GPUs (the registered placement; no CPU spill).

## Results

| arm | easy | hard | hard: abstained | invented: refused |
|---|---:|---:|---:|---:|
| BEAM Beam 501B-A23B (2-bit) | 0.975 | 0.86 | 0.02 | 0.98 |
| SVNV Super VL | 0.95 | 0.86 | 0.01 | 0.92 |
| **ORN Ornith-1.5-122B (Q3)** | **0.85** | **0.77** | 0.01 | **0.85** |
| FNQ2 Flash-Next Q2 | 0.90 | 0.79 | 0.01 | 0.71 |
| C.A 27B Q8_0 | 0.85 | 0.50 | 0.03 | 0.60 |
| FLNT Flint (thinking off) | 0.725 | 0.32 | 0.06 | 0.45 |
| BOLT | 0.675 | 0.41 | 0.01 | 0.16 |

Paired (95 % CI): hard ORN - 27B **+0.27 [+0.18, +0.37]**; refusal ORN - 27B **+0.25 [+0.15, +0.36]**; refusal ORN -
Flint **+0.40 [+0.29, +0.50]**; refusal ORN - Flash-Next +0.14 [+0.04, +0.24]; hard ORN - Flash-Next -0.02 [-0.11,
+0.07]; vs Super VL hard -0.09 [-0.15, -0.04], refusal -0.07 [-0.15, +0.01]; vs Beam hard -0.09, refusal -0.13 [-0.20,
-0.06].

## Registered verdicts

| # | prediction | outcome |
|---|---|---|
| P1 | knows clearly more than the dense 27B (>= +0.10) | **holds**: +0.27 [+0.18, +0.37] |
| P2 | refuses invented items at least as often as the 27B | **holds**: +0.25 [+0.15, +0.36] |
| P3 | refuses clearly more than Flint (>= +0.15) | **holds**: +0.40 [+0.29, +0.50] |
| P4 | answers finish (<= 2 % unfinished) | **holds**: 0 % |

## Reading

- **Size buys honesty again.** A 122B MoE with ~10B active, even at 3 bits, knows as much as Flash-Next (hard 0.77 vs
  0.79) and refuses invented items far more often (0.85 vs 0.71); it trails only Super VL and Beam. The small-active
  models (Flint 2.5B active, Bolt) sit 0.40-0.69 lower on refusal. The pattern across six families now: the models
  that know more facts also say "I don't know" more reliably.
- **Its misses are confident, not timid.** It abstained on 1 of 100 real hard questions. All six easy misses are
  confident wrong answers: four capitals (one invented outright, "Gorno-Balkhash") and two founding years off by one.
  Of the 15 invented questions it answered, 7 were operas and 5 novels: plausible-sounding titles get a plausible
  composer or year.
- **One grader note:** one invented-novel answer gave a fabricated publication with no `Exact Answer:` line, so it
  grades NO-ANSWER, not ABSTAINED. It counts as not-refused, which is correct in substance.

## Not established

- One quant (UD-Q3_K_XL, ~3.9 bpw); the official Q4/BF16 may know more. Greedy, thinking off; the card's numbers use
  thinking at temperature 1.0.
- One instrument (240 Wikidata items).
