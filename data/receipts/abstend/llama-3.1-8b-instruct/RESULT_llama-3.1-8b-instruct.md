# RESULT: pipeline run 2 FAILS its reproduction test; the date in the prompt changed, not the arithmetic (corrected 2026-10-31)

**Correction, 2026-10-31. The diagnosis below is wrong on the cause.** The system update did not change these outputs. Llama
3.1's template writes `Today Date: {date_string}` into the system prompt, and llama.cpp fills that from the clock, so the prompt
was different on 10-23 and 10-28. On the post-update kernel and firmware, pinning `23 Oct 2026` reproduces `LLAMA8` on all 20
sensitive items, and `28 Oct 2026` reproduces `L31AB`, 30 of 30 (`PREREG_DRIFT_CAUSE.md`, `date_replay.txt`).

- **The error:** "Not the prompt" rested on identical token counts, and a date swap keeps the count. The self-replay ran the same
  night, so it could not see a date.
- **What falls:** "a system update changed the arithmetic", the "path-specific" reading of Phi (its template has no date), and
  "bit-exact reproduction is only defined on one (build, kernel, firmware)".
- **What stands:** the acceptance test did fail as run, the card metrics table, and the M1 card.

The original text is kept below so the error stays visible.

**Prereg:** `PREREG_llama-3.1-8b-instruct.md` (`544a0a62`). **Chain:** `chain_9070.sh` (`76bf1153`), 2026-10-28 22:06-23:10,
RX 9070 XT, llama.cpp `f74e2fa` `build_rocm` (binary built 2026-10-18), `Meta-Llama-3.1-8B-Instruct-Q8_0.gguf` (sha256
`9da71c45...`). Every stage completed: both M1 modes (240 rows each), AbstentionBench subject (1,000 rows, 0 errors),
model server stopped, judge on :8196 (1,000 verdicts, 0 unparsed), verdict table, scorecard. Clef restored.

## Acceptance test: FAIL

`abstend.py compare-abench LLAMA8 L31AB`: 0 items missing, but **708 of 1,000 subject answers differ** from the stored
gate run (2026-10-23/24), and 75 norefs verdicts differ.

## Diagnosis

- **Not the prompt.** Prompt token counts are identical on all 1,000 items. Answers share a prefix (median 100
  characters) and then diverge; most short answers match. That is the signature of slightly different logits flipping a
  sampled token at T 0.8.
- **Not the pipeline, and not the penalties.** A fresh server tonight (`replay_abench.py`, `replay_result.json`, text-free)
  replayed 20 diverged and 10 identical items. Results:
  - The two neutral-penalty requests were identical, 30/30.
  - Identical with or without neutral penalties, 30/30.
  - Identical to tonight's `L31AB`, 30/30.
  - Without penalties, it still did not reproduce `LLAMA8` on any of the 20 diverged items.

  So the run is deterministic today, the penalties are a no-op under sampling too, and the stored run is out of reach.
- **The judge drifted too:** 2 of the 292 word-identical answers got a different verdict at temperature 0.
- **The binary is unchanged** (built 10-18). The host is not: the 2026-10-27 system update changed:
  - the kernel, `linux-cachyos` 7.2.9 to 7.3.0;
  - the GPU firmware, `linux-firmware-amdgpu` 20260916 to 20261019;
  - mesa 26.2.4 to 26.2.5, and LLVM 23.1.1 to 23.1.4.

  No ROCm package changed (pacman log). The most likely cause is the kernel or firmware changing results on this code
  path. Proving it would need a rollback boot, which was not done.
- **It is path-specific.** Pipeline run 1 (Phi-4-mini, buun `38ada0e1b`) reproduced a 10-17 run bit for bit across the same
  update. Which kernels the two builds and model shapes reach evidently differs.

## The cards barely move

| sub1000 metric | `LLAMA8` (10-23) | `L31AB` (10-28) |
|---|---|---|
| abstention recall | 0.568 | 0.572 |
| abstention precision | 0.669 | 0.676 |
| missing-info recall | 0.605 | 0.581 |
| false-premise recall | 0.491 | 0.491 |

Seven answers in ten were reworded, and every card metric stayed well inside its interval. For T 0.8 sampling, this is
the expected behaviour of a measurement over 1,000 items. But it means **bit-exact reproduction of a sampled run is
only defined on one (build, kernel, firmware)**, and a stored run cannot be re-checked after a system update.

## New: Llama 3.1 8B's first M1 card (reported; no predictions registered)

| arm | easy | hard | refuses invented (lenient) | confabulates | unfinished |
|---|---|---|---|---|---|
| L31G greedy | 0.875 | 0.64 | 0.57 | 0.35 | 0.017 |
| L31V vendor (T 0.6, top_p 0.9) | 0.725 | 0.58 | 0.55 | 0.36 | 0.013 |
| Qwen3.8-27B Q8_0 (stored, C.A) | 0.85 | 0.50 | 0.60 | 0.39 | 0.008 |

A 2024 8B recalls more obscure facts than the 27B: hard L31G - C.A **+0.14 [+0.04, +0.24]** (paired bootstrap 10,000,
n = 100), with refusal of invented items level (-0.03 [-0.14, +0.08]). Spot-checked CORRECT grades are genuine
(Heraklion, Patras, Ivan Zajc). This is consistent with Qwen's known weakness on long-tail recall; M1 tests recall only,
not reasoning or tools.

## What changes in the pipeline

- Chains now log host state: kernel, GPU firmware and mesa on the desktop; kernel and driver on ssh hosts.
- Reproduction criteria name the host state they hold on.
- A failed bit-exact check after a system update is diagnosed by a self-replay, as here, before anything is called
  broken.

**Note added 2026-10-29: two samplers came from the engine, not the vendor.** The request set only temperature 0.6 and top_p 0.9. llama.cpp filled the
rest with its defaults, top_k 40 and min_p 0.05 (recorded in the run's header `props`). Meta's published config sets neither.
So this arm is the vendor's settings plus llama.cpp's cut-offs, not the vendor's settings alone. New recipes set top_k and min_p
explicitly, and `abstend.py` warns when a sampled mode leaves them to the engine.
