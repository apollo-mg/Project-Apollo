# RESULT (phase 1 of 2): DaisyRose-27B, an RL-only FULL fine-tune of Qwen3.8-27B, leaves refusal of invented questions exactly where it was (60 of 100, not one item changed) -- so it is the RL, not the pi adapter's small size, that kept "I don't know"

**Prereg:** `PREREG_DAISYROSE.md` (committed before any run). **Run:** 2026-11-21, `run_daisyrose.sh`, code `b43cbf11`;
log `daisyrose.log`. Phase 2 (the agentic items) is running; its result will be added here.

## The file and the gates

- RadixArk/DaisyRose-27B @ `64a4ec66`, BF16, all 30 files size- and sha256-checked against the Hub (`files.txt`),
  converted with llama.cpp `67107ac34f --outtype q8_0` as Arete was: 29,047,084,480 bytes, sha256 `067d9ece...`.
- **Tensor map against the base Q8_0:** 866 tensors each, the same names and types (506 Q8_0, 360 F32), nothing
  only in one file (`tensor_map.txt`). The two files differ in their weights only.
- Staged on .194 (403 GB free), both hashes verified there. **Prompt gate:** token-identical prompts on both servers
  (`766e6600...`, 240 prompts).
- **D0, the base replay:** C.R4 matches the stored ceiling C.A on 240 of 240 grades and 240 of 240 response texts,
  byte for byte. **Holds.**

## Phase 1: M1 (DRS vs C.R4, paired over 240 items, thinking off, greedy)

| | base (C.R4) | DaisyRose | difference [95% CI] | flips (DRS only / base only) |
|---|---|---|---|---|
| easy real correct (40) | 0.85 | 0.825 | -0.025 [-0.075, 0.000] | 0 / 1 |
| hard real correct (100) | 0.50 | 0.51 | +0.01 [-0.02, +0.04] | 2 / 1 |
| invented, refused (100) | **0.60** | **0.60** | **0.00 [0.00, 0.00]** | **0 / 0** |
| invented, answered anyway | 0.39 | 0.40 | +0.01 | 1 / 0 |
| unfinished (240) | 0.008 | 0 | -0.008 | 0 / 2 |

Mean R-slot P(UNKNOWN): hard 0.061 -> 0.070, invented 0.699 -> 0.727.

| | result |
|---|---|
| D0 base replay >= 238 of 240 | **holds**: 240, byte-identical |
| D1 hard accuracy within +/-0.05 | **holds**: +0.01 |
| D2 the question | **the RL reading holds**: 0.00, CI [0.00, 0.00]; not one invented item changed its grade. Predicted at 0.55 |

## Reading

1. **RL leaves "I don't know" alone; SFT and distillation take it away.** Five variants made by imitation, editing or a
   point release each refused fewer invented questions (by 7 to 19 points). The two made by reinforcement learning --
   a rank-32 LoRA stopped early (the pi adapter) and a full-weight fine-tune with about 63,000 H200-hours
   (DaisyRose), from different teams, harnesses and task sets -- left it exactly where it was. The pi adapter's
   result was not about its small size.
2. **RL moves the model less on what it was not trained for, at any size.** Against the stored base, DaisyRose
   changed the text of 135 of 240 answers and 6 grades; the pi adapter 112 and 8; Arete (SFT) 223 and 24; Qwopus Coder
   (distillation) 204 and 21. The full-weight RL run has a footprint on facts like the small LoRA's, not like the SFT
   runs'. This fits the argument that on-policy RL forgets less (it learns from its own samples, never imitating a
   teacher's always-answering text).
3. **The same items flip in both RL variants (exploratory).** Four of DaisyRose's six grade changes are the pi
   adapter's too (an easy item lost, two hard items gained, one truncation now answered). These look like items on a
   knife-edge for the base, where any small change tips the answer, not like a shared learned behaviour.

## Limits

Two RL variants of one base; thinking off (DaisyRose was benchmarked, and probably trained, with thinking on; the
registered caveat cuts against a drop, and there was none); 100 invented items; greedy.
