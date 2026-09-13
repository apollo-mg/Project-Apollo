# Result — at a distribution tie, the task is a tie too: EXL3 3.00bpw and UD-IQ3_XXS solve the same problems, and EXL3 does it in ~1 GB less

**Run 2026-09-13, 16:38:56–18:02:20, `.194`** (4× P100, sm_60), EXL3 campaign test 11, ledger O6. Pre-registered in
`PREREG_EXL3_USABLE.md` with Amendments 1–5. Driver `exl3_usable.py`, scorer `tools/score_exl3_usable.py`, harness
`hep_eval.py` **unmodified** — all committed before the run. HumanEval+, 164 problems, K=1 at temperature 0,
thinking off, one chat template pinned by file across both arms. **Both arms exited rc=0 and completed all 164
problems**, so the full-N pairing applies and Amendment 1's partial-run rule was not needed.

Arms ran **side by side**, one socket and two cards each (Amendment 3): EXL3 on GPUs 0–1 / NUMA 0 / port 8101,
GGUF on GPUs 2–3 / NUMA 1 / port 8102. Both files hash-verified on the node before inference (Amendment 4).

## The pair, and why it is this pair

Chosen **after** test 10, disclosed as post-data in Amendment 2 — test 10's selection rule turned out to be
ambiguous, and the ambiguity was only visible with the curve in hand:

| side | file | peak VRAM (test 10) | mean KLD (test 10) |
|---|---|---|---|
| **EXL3** | EXL3 3.00bpw | 10,568 MiB | 0.046152 ± 0.001743 |
| **GGUF** | unsloth UD-IQ3_XXS rev `f9758630` | 11,532 MiB | 0.047609 ± 0.001210 |

The two are a **distribution TIE** by test 3's rule — 3% apart, inside the summed uncertainties — while EXL3 uses
**964 MiB less**. The question is therefore not "does lower KLD win", but: **when two files are indistinguishable
in distribution, do they behave the same on a task, and is the VRAM saving free?** GGUF is not handicapped; it
holds more VRAM and the marginally lower KLD.

## Result

| arm | solved (greedy, 164) | PASS | WRONG | EXEC_TIMEOUT | mean out tokens | thinking |
|---|---|---|---|---|---|---|
| EXL3 3.00bpw | **152** (92.7%) | 152 | 11 | 1 | 227 | 0 samples |
| UD-IQ3_XXS `f9758630` | **151** (92.1%) | 151 | 12 | 1 | 205 | 0 samples |

**Paired:** +0.6 points, discordant **4 EXL3 / 3 GGUF**, **157 tied**, two-sided sign test **p = 1.000**.

**95% CI on the paired difference: [−2.7, +3.4] points** (Clopper–Pearson on the 7 discordant pairs, mapped back
to 164 problems). **Both bounds sit inside Mark's 5-point bar** — so this run does not merely fail to find a
substantial difference, it **excludes one** in either direction. That is the strongest statement K=1 supports here,
and it is a real one.

## The two arms fail the *same problems*

This is the finding, and it is stronger than the headline number:

- **9 of the failures are shared** — WRONG on HumanEval/32, 76, 91, 95, 97, 132, 141, 145, plus the **same
  EXEC_TIMEOUT on HumanEval/163** in both arms.
- **EXL3-only failures: 3** (HumanEval/22, 77, 93). **GGUF-only failures: 4** (HumanEval/101, 134, 151, 154).
- EXL3 fails 12, GGUF fails 13, and **9 of those are the same problem in both**.

Seven problems separate two files that differ by a whole quantization format. **The failure set is a property of
the model and the benchmark, not of the quantizer** — the residual disagreement is at the size where a coin flip
explains it (4:3). A quantization difference that mattered would show as *different* problems failing, not the
same nine plus noise; it doesn't.

## Predictions

| id | prediction | result |
|---|---|---|
| P-U1 | EXL3's pass@1 exceeds the GGUF's | **NO DETECTABLE DIFFERENCE** — +0.6 points, p = 1.000. The prereg's rule: report a difference only at p < 0.05 |
| P-U2 | the difference is substantial (≥ 5 points) | **FALSIFIED** — +0.6 points, and the 95% CI excludes ±5 |
| P-U3 | EXL3 produces fewer degenerate outputs | **FALSIFIED as coded, vacuous in substance** — see below |
| P-U4 | both arms clear 50% | **CONFIRMED** — 92.7% and 92.1% |

**P-U3 is a scoring artifact and is recorded as one.** Amendment 4 scored it on `TRUNCATED` + `NO_ANSWER` bucket
counts. **Both arms produced zero of either**, and the scorer's rule (`exl3 < gguf`) returns false on 0 < 0, so it
printed FALSIFIED. **The honest reading is that the prediction had nothing to discriminate:** no degeneracy
occurred in either arm, at 8,192 context with a 4,096-token cap. Mean output tokens — the other quantity
Amendment 4 named — go 227 (EXL3) vs 205 (GGUF), an 11% difference with no truncation in either arm; that is
verbosity, not collapse, and it is not evidence for P-U3 in either direction.

**P-U4 was written to be able to sink the argument** — if both models at ~3 bpw failed most problems, EXL3's
compression advantage would land below the usability floor. It doesn't: both arms are at ~92%, comfortably usable.

## Amendment 5's KV check — delivered, and positive

Both arms logged `KV []` during the run because buun's server prints no `K (…)` / `V (…)` lines at default
verbosity, making the driver's f16 guard a check that could not fail. Amendment 5 promised the real check after
the run: reload each arm's exact command with `-lv 4`, load only, no requests.

**Run 18:37–18:38, both arms, results in `usable/kvload_{exl3,gguf}.log` and `usable/kvcheck.log`:**

| arm | K/V types | layers | model buffers |
|---|---|---|---|
| exl3 | **K (f16), V (f16)** | 66/66 offloaded | CUDA0 4,522.23 + CUDA1 5,155.69 = **9,677.9 MiB** |
| gguf | **K (f16), V (f16)** | 66/66 offloaded | CUDA0 5,117.25 + CUDA1 5,641.13 = **10,758.4 MiB** |

Both also report `n_ctx = 8192`, `flash_attn = enabled`, `kv_unified = true`. **The absolute f16 claim now holds
for both arms**, not just the relative one — neither silently ran buun's VBR default ([[buun-default-kv-is-vbr]]).
The weight buffers independently reproduce the size gap: **1,080 MiB in EXL3's favour**, alongside test 10's
964 MiB peak-VRAM figure.

## What this means for Mark's bar

**Mark's bar was "a substantial difference in usable quality".** Test 10 gave the distribution side: EXL3 is
1.33–1.45× closer to the reference at matched VRAM, worth 5–10% of memory. **Test 11 gives the task side, and the
answer is that the tie transfers.** At a distribution tie, the task result is a tie too — with the saving intact.

So the case for EXL3 on this model is **not** that it answers better. It is that it reaches the same answers in
~1 GB less VRAM. That is a real, if modest, argument, and it is the one the campaign can defend. Against it on
Pascal, unchanged from test 10: EXL3 decodes at 0.646× the daily driver as served, and gets less from MTP
(1.24× vs 1.69×). **A ~9% VRAM saving that costs ~35% of decode speed is not a trade this fleet should take** —
but on hardware where EXL3's kernels are not the bottleneck, the same saving is close to free.

## Deviations and limits

- **The arm pair was chosen post-data** (Amendment 2), because test 10's selection rule was ambiguous between its
  two envelopes. Disclosed at the time, in the prereg, before this test ran.
- **P-U3's verdict is a scoring artifact** on a 0-vs-0 comparison; recorded above rather than quoted as a result.
- **K=1, one benchmark, one language.** Each figure is "solved this problem greedily", not a deployment rate.
  HumanEval+ is Python code generation; tool-call and JSON-schema adherence is the axis this repo actually runs on
  and is a separate test, as the prereg declared.
- **Wall clock is not scored** (Amendment 3, arms concurrent). Recorded only as an observation: both arms ran
  16:39:44 → 18:02:15, finishing within the same second, with EXL3 emitting 11% more tokens over that span.
  The arms shared a host, so this is not a speed comparison and must not be quoted as one.
- **This cannot separate format from quantizer.** One EXL3 quantizer at one setting against one packager's recipe.
- **The EXEC_TIMEOUT on HumanEval/163** is a harness/runtime artifact, identical in both arms, and counted as a
  failure in both — it cannot bias the pairing.

Artifacts: `usable/` — `results.jsonl`, `usable_results_{exl3,gguf}.json`, `hep_{exl3,gguf}.log`, `driver.log`,
`manifest_exl3_300.txt`, `published_gguf.json`, `provenance_sweep.log`, `kvload_{exl3,gguf}.log`, `kvcheck.log`.
