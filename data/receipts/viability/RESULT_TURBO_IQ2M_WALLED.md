# RESULT: DavidAU TURBO IQ2_M — runs away on anything non-trivial; VBR and MTP exonerated

**Date:** 2026-09-09 · **Hardware:** RX 9070 XT · **Build:** buun `3823c9eb6`
**Model:** `Qwen3.8-27B-TurboFCFusion-735-882-Here-Uncen-NEO-CODER-MAX-MTP-IQ2_M.gguf` (11.29 GiB)
**Config:** `-c 32768 -np 1 -fa on --kv-unified -ctk vbr -ctv vbr --vbr-floor t2 --vbr-vram auto`,
**no `--spec-type`** (MTP deliberately disabled) · **Bench:** hermesbench, fixed grader

## Why MTP was off

Isolation, per Mark: **VBR > MTP in priority.** *"Speed /= goodness."* VBR is the subsystem we want
working; MTP carries a known defect (`RESULT_TIMEOUT_WALL_ROOT_CAUSE.md`). Running with MTP would
have made this result uninterpretable.

**The isolation worked and is the most valuable part of this run.**

## Result: walled after 6 tasks

| | |
|---|---|
| attempted | 12 of 61 (killed — every remaining task was 360 s of nothing) |
| PASS | 6 (all `t01_terminal_smoke` + `t02_read_head`) |
| INFRA_ERROR | 6 (consecutive, no recovery) |

Per-request generation length, in order:

```
[100, 175, 100, 100, 100, 8332, 8334, 8393, 8518, 8452, 8640]
 <----- trivial tasks ----->  <-------- runaway, never recovers -------->
```

**Nothing between 479 and 8,332 tokens.** The model either answers in ~100 tokens or generates until
the harness kills it (~8,300 tokens ≈ 360 s × 24 t/s). `t03_patch_edit_t01_basic` did not recover,
confirming this is not one hard family.

## VBR and MTP are both exonerated

| signal | value | meaning |
|---|---|---|
| VBR floor clamps | **0** | the tier clamp never fired |
| VBR watermark | **13,312, flat** | vs the 21,504 that triggered the MTP collapse |
| context checkpoints | 27 | no runaway accumulation |
| draft/spec log lines | **0** | MTP genuinely absent |
| decode | **24–25 t/s, stable throughout** | no degradation |

Neither subsystem we spent the night on is involved. **This is the quantisation.** That
discrimination is only possible because MTP was disabled first — with it enabled, this would have
been indistinguishable from the acceptance collapse.

## Prediction scorecard

| prediction | claim | outcome |
|---|---|---|
| P1 (75%) | completes 61 tasks without a wall | **FALSIFIED** — walled at 6 |
| P2 (60%) | decode 27–32 t/s | **FALSIFIED** — 24–25 |
| P3 (55%) | IQ2_M shows degradation IQ3_XXS did not | **CONFIRMED** |
| P4 (70%) | valid_pass_rate below 0.943 | **UNSCORABLE** — see below |

**P2's error:** I derived the band by dividing the IQ3_XXS rate by the MTP multiplier, ignoring that
**IQ2_M's dequantisation path costs more per weight than IQ3_XXS's.** A smaller file is not a faster
model when the format is more expensive to unpack.

## The verdict schema produced its most misleading number yet

`valid_pass_rate = 6/6 = **1.000**`

**A model that cannot complete a single non-trivial task scores a perfect pass rate**, because every
failure was classified INFRA_ERROR and left the denominator. This is the third time in one campaign
the same schema defect has produced a flattering headline (the `fixed_grader` 1.0; det02's 0.943
pre-rescore; now this). It is the strongest argument yet for splitting the verdict schema —
`RESULT_CORPUS_HARDENING_GOLDEN.md` item 4, now promoted to first priority.

## The 2-bit control panel (all present locally)

The TURBO result confounds three variables: bit depth, quant format (IQ2_M), and model lineage
(a DavidAU merge). Same-base-model variants on disk separate them:

| model | GiB | isolates |
|---|---|---|
| `GSQ-RCO-IQ3_XXS-mtp` | 9.73 | 3-bit baseline (measured: valid_pass_rate 0.943) |
| **`GSQ-RCO-IQ2_XS-mtp`** | **8.17** | **bit depth alone** — same base, family, MTP |
| **`UD-IQ2_M`** | **9.61** | **same format, different recipe** — isolates the merge |
| `UD-Q2_K_XL` | 9.15 | unsloth K-quant allocation |
| `AD-IQ2_XS` | 9.21 | a third recipe at nominally the same depth |

**`UD-IQ2_M` is the sharpest single control**: same nominal format as TURBO, different packager,
unmerged base. Runaway there implicates the format; clean there implicates the merge.

**Note the spread: 8.17 → 11.29 GiB across models all labelled "2-bit."** Nothing below 3 bits is
uniform any more — every surviving recipe is a *dynamic allocation* scheme keeping attention,
embeddings and output at higher precision. So these comparisons measure **where a recipe spends its
bits**, not bit depth. Same lesson as `gguf-label-is-not-a-spec`, and the same principle as VBR,
which the whole sub-3-bit field converged on independently for weights.

## Open

What the runaway actually contains — a repetition loop (quantisation degeneration) versus coherent
but endless reasoning (a stopping-rule failure). These are different findings with different
implications, and the diagnostic probe has not yet returned a clean capture.

---

# SEPARATE BUG FOUND WHILE DIAGNOSING: `max_tokens` does not bound generation

> **CAVEAT ADDED 2026-09-09 — this observation may be contaminated; treat as UNVERIFIED.**
>
> The `max_tokens: 400 -> n_gen 14,039` reading was taken **minutes after killing the TURBO bench**.
> Per **AFM-36**, killing `hermesbench run` leaves its `run_agent.py` child alive and generating.
> Task 52065 may therefore have been *the orphan's* request, not mine — I identified it by being the
> most recent task in the log, which is exactly the wrong way to identify a request when another
> process is issuing them.
>
> **What is independently confirmed** (2026-09-09, clean server, process tree verified, no orphans):
> server-side `-n 4096` does not bound all generations — two requests reached **8,185** and
> **12,990** tokens against that cap. So the *class* of defect (token budgets not reliably enforced)
> is real. The specific `max_tokens` figure above is not trustworthy and needs re-measuring on an
> idle server before it is quoted anywhere.

Attempting to capture a runaway's *content* by re-sending a file-read prompt with
`{"max_tokens": 400}`, the request never returned. Server state at the time:

```
task 52065 | n_gen = 14039, tg = 25.23 t/s     <- request sent with max_tokens: 400
/slots -> slot 0: is_processing = True
```

**14,039 tokens against a 400-token cap — 35× over, and still generating.**

`max_tokens` in the OpenAI-compatible API is specified to bound **all** completion tokens, reasoning
included. On this build it does not bound `reasoning_content` at all. Two earlier requests in this
session with `max_tokens: 96` returned promptly, so the cap is not universally ignored — it appears
to bound *visible content* while leaving the reasoning channel unbounded, which only becomes visible
on a model that reasons without converging.

## Why this matters more than the model result

- **The 360 s harness timeout is the only backstop.** Every runaway tonight (~8,300 tokens ≈ 360 s ×
  24 t/s) was terminated by the *client*, not by any server-side limit.
- **Anyone using `max_tokens` as a safety bound on a reasoning model is unprotected.** That is the
  natural, documented way to bound cost and latency, and it silently does not work here.
- Server-side `n_predict` *does* bound generation (the tier_cal fixture's escalation
  `[6144:length -> 12288:length]` shows it working), so the two paths differ.

## Reproduction

Any reasoning model on this build, any prompt that induces long reasoning:

```
curl .../v1/chat/completions -d '{"messages":[...],"max_tokens":400}'
# observe n_gen in the server log climb past 400 without bound
```

Build: buun `3823c9eb6`, RX 9070 XT / ROCm. Not yet checked against upstream llama.cpp or against
`a56eeef5`+ — **do not report as fork-specific without that check.**

## Consequence for the corpus work

This is a second, independent argument for **token-budget caps enforced server-side** rather than
wall-clock timeouts (`RESULT_CORPUS_HARDENING_GOLDEN.md` item 2). A client-side `max_tokens` cannot
be relied on, so the budget has to be set with `n_predict` where the server will honour it.
