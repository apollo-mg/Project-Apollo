# Result -- Recursive Flint (40B, 2.5B active) knows the least of any model on the instrument but Bolt (hard 0.32) and refuses only 45 of 100 invented questions; thinking changed nothing but the cost (hard 0.32 both, refusal 0.39, 2.65 h vs 8 min, 11 runaways)

**Prereg:** `PREREG_FLINT.md` (`520ec4ce`, before any Flint row). **Analysis:** `analyze_flint.py` -> `RESULT_flint.json`.
**Raw:** `raw/main_FLNT.jsonl`, `raw/main_FLTK.jsonl` (240 rows each, `--usage`), `raw/flint_state.log`.

**Run (2026-10-21 23:30 -> 2026-10-22 02:18, unattended):** Unsloth `flint-Q8_0.gguf` (sha256 verified), .194 4x P100
150 W, upstream llama.cpp `c7fc509`, `-sm layer -c 32768 -np 1`, client on the desktop. FLNT: server
`--reasoning-budget 0`, smoke gate passed (content, no reasoning). FLTK: fresh server without a budget, smoke gate passed
(content and reasoning). Greedy.

## Results

| arm | easy | hard | hard: abstained | invented: refused | unfinished | median tokens | median s/answer | arm time |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **FLNT** Flint, thinking off | 0.725 | **0.32** | 0.06 | **0.45** | 1.3 % (3) | 29 | 1.3 | 8 min |
| **FLTK** Flint, thinking on | 0.70 | **0.32** | 0.03 | **0.39** | 4.6 % (11) | 681 | 15.4 | 2.65 h |
| BEAM (stored) | 0.975 | 0.86 | 0.02 | 0.98 | 0 | | | |
| SVNV Super VL | 0.95 | 0.86 | 0.01 | 0.92 | 0 | | | |
| FNQ2 Flash-Next Q2 | 0.90 | 0.79 | 0.01 | 0.71 | 0 | | | |
| C.A 27B Q8_0 | 0.85 | 0.50 | 0.03 | 0.60 | 0 | | | |
| BOLT | 0.675 | 0.41 | 0.01 | 0.16 | 0 | | | |

Paired (95 % CI): hard FLNT - 27B **-0.18 [-0.29, -0.07]**; refusal FLNT - 27B -0.15 [-0.26, -0.05]; refusal FLNT -
Super VL -0.47 [-0.57, -0.37]; refusal FLNT - Bolt +0.29 [+0.19, +0.39]; hard FLNT - Bolt -0.09 [-0.21, +0.03]. Thinking:
hard FLTK - FLNT **0.00 [-0.08, +0.08]**, refusal **-0.06 [-0.15, +0.02]**.

## Registered verdicts

| # | prediction | outcome |
|---|---|---|
| P1 | 2.5B active knows no more than the dense 27B | **holds**: hard -0.18 [-0.29, -0.07] |
| P2 | refuses invented items clearly less than Super VL | **holds**: -0.47 [-0.57, -0.37] |
| P3 | thinking makes it refuse more (>= +0.05) | **does not hold**: -0.06 [-0.15, +0.02], if anything the other way |
| P4 | answers finish (<= 2 % unfinished, both arms) | **does not hold**: FLTK 4.6 % (11 hit the 8,192-token cap: 7 invented, 4 hard); FLNT 1.3 % |

## Reading

- **Small active parameter count, small knowledge.** Flint's hard accuracy (0.32) is the lowest measured here except
  Bolt's (0.41, within noise), 0.18 below the dense 27B. Its coding and instruction-following scores do not carry over
  to factual recall.
- **It invents answers to more than half the fictional questions** (refuses 0.45): better than Bolt (0.16), worse than
  the 27B (0.60), far from Super VL and Beam (0.92-0.98).
- **Thinking bought nothing here.** Same hard accuracy to the item count (0.32 = 0.32), no more refusals, 20x the time
  per answer and 4.6 % runaways that never answered, mostly on invented questions. That repeats the Qwen3.8 `xhigh`
  finding (`viability/RESULT_EFFORT_SWEEP.md`: abstentions became non-termination) and the Beam effort result
  (`RESULT_BEAM_EFFORT.md`: effort above minimal changed nothing) on a third model family. For factual lookups, run
  reasoning models with thinking off.
- **Fit with the session-state result:** Flint follows formats well and is fast, but neither extracting nor knowing
  is its strength. A good fit for structured tool plumbing on fast hardware; not for memory, retrieval-free facts or
  trust-sensitive answers.

## Not established

- One quant (Q8_0), greedy decoding; Flint's published scores average five samples at temperature 1.
- One instrument (240 Wikidata items); coding and agentic tasks are not measured here.

**Operational note:** the chain's final `s194.sh off` refused because the server had been signalled a moment earlier
and was still exiting; .194 was powered off by hand at 02:20. `flint_chain.sh` now waits for the PID to exit first.
