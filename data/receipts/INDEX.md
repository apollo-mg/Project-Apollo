# Findings index — keyed by MECHANISM, not by experiment

**Why this exists.** On 2026-08-16 a day of work re-derived at least six things already sitting
in this directory: that prompt-cache reuse changes temp-0 output, that batch composition changes
it upstream too, that MTP's instability is an MTP x prompt-caching interaction rather than MTP
alone, that MTP's nondeterminism lands differently by content type, that `--reasoning-budget`
had already been characterised, and that running a model at temp 0 outside its recommended
sampling envelope costs wall-clock and serving stability.

None of that was lost. It was **unfindable**, because 168 receipts are named after the
experiment that produced them, and the lookup you actually need is *"has anyone here already
touched this mechanism?"*

`FAILURE_MODES.md` catalogues how we get things wrong. This catalogues what we already know.
Grep this file before designing anything.

**Rule: when a receipt lands, add a line here.** One line, the mechanism tags that would make
someone find it, and the claim in a form that is checkable.

---

## determinism · reproducibility · temp-0

| finding | receipt | date |
|---|---|---|
| Temp-0 nondeterminism has **two independent causes**; concurrent batched decoding is **present upstream**, `-np 1` is the control | `hermesagent20/DETERMINISM_ROOT_CAUSE.md` | 07-27 |
| Prefix-cache reuse changes temp-0 output **on genuine upstream**; `cache_prompt=true` is the DEFAULT, `--no-cache-prompt` required to avoid | `hermesagent20/PREFIX_CACHE_CHANGES_OUTPUT.md` | 07-27 |
| **MTP is deterministic at temp 0.** The instability was MTP x prompt-caching, not MTP | `battle16gb/MTP_CACHEPROMPT_FALSIFICATION.md` | 07-30 |
| MTP nondeterminism lands by content type: **prose drifts, tool calls hold, code breaks** | `battle16gb/MTP_STRUCTURED_OUTPUT.md` | 07-29 |
| Upstream knows the MTP mechanism; MTP tensors load even when never requested | `battle16gb/MTP_UPSTREAM_ROOT_CAUSE.md` | 07-30 |
| f16 control is **bistable within one build** on Polaris — byte comparison at K=1 is invalid there | `battle16gb/F16_CONTROL_BISTABLE.md` | 07-31 |
| Speculative decoding never reproduced non-speculative output (0/12) — **NEEDS RE-RUN with `cache_prompt:false`**, see falsification above | `spec-decode-determinism/RESULT_SPECULATION_IS_NOT_BIT_EXACT.md` | 08-15 |
| Agent benchmarks on `.73` are not reproducible at K=1 (HA-04 bistable 35/100/100/35) | `battle16gb/HA20_BASE_K3_CONTROL.md` | 07-30 |

## sampling · envelope · reasoning effort

| finding | receipt | date |
|---|---|---|
| Running at temp 0 **outside the model's recommended envelope** cost 18x wall-clock and a hard serving failure | `scrapebench/SAMPLING_ENVELOPE_QWOPUS.md` | 08-01 |
| `--reasoning-budget`: the same flag does **opposite things** on two arms; a bounded budget rescues both | `battle16gb/reasoning_budget_smoke/RESULT_REASONING_BUDGET_SMOKE.md` | 08-08 |
| `reasoning_effort` is a **chat-template variable** defaulting to `xhigh`; `low` took HLE parse 0%->80% at 6.3x fewer tokens | `hle-mini/POWER.md` | 08-16 |
| Thinking **compensates for quantisation damage** — gap collapses 25.0pp -> 3.3pp from Q2 to IQ4 | `battle16gb/PUZZLE_LADDER_FA_ON.md` | 07-17 |
| Thinking suppression is an **interaction**: persona x tools, not either alone | `thinking-suppression-2x2/SUMMARY.md` | 07-26 |
| **The "temp 0.6 for coding" advice is 3.6-era and obsolete on 3.8.** 3.6's template has no `reasoning_effort`, so the card offered a *third* sampling set (thinking/coding, temp 0.6) alongside thinking/general (1.0) and instruct (0.7). 3.8 added the effort dial and dropped the coding set. The knob moved from sampling params (visible everywhere) into the chat template (visible nowhere) | verified from `tokenizer_config.json`, both repos | 08-16 |
| Temperature 0 vs 1.0 moved HLE parse rate **not at all** (20% both); `reasoning_effort` moved it 0%->80%. On this task the temp knob is close to irrelevant next to the effort knob | `hle-mini/POWER.md` | 08-16 |
| Unbounded tool-call arguments at Q4 and Q6 alike — a merge defect, not a quant defect | `scrapebench/QWOPUS_RUNAWAY_ROOT.md` | 08-01 |

## speculative decoding · MTP · drafters

| finding | receipt | date |
|---|---|---|
| MTP n-max: **dense and MoE have different optima, for different reasons**; dense wins bigger | `pulsar/MTP_DENSE_VS_MOE_NMAX.md` | 08-03 |
| MTP on 2xP100 MoE: 70.5 t/s, and the **n-max ceiling is set by the MMVQ batch table** | `pulsar/MTP_PASCAL_NMAX_MMVQ.md` | 08-03 |
| MTP on Qwen3.8-27B / RDNA4 is **2.05x faster**; two public "slower" reports do not reproduce | `qwen38-mtp/RESULT_RDNA4.md` | 08-14 |
| DFlash (block-diffusion drafter) beats the MTP head 1.34-1.40x; **content split** — DFlash wins code/SQL/JSON, MTP wins prose | `qwen35-drafters/RESULT_MTP_VS_DFLASH.md` | 08-15 |
| MTP draft head is **quantised blind** — no packager's imatrix covers `blk.64` | `qwen38-packagers/RESULT_MTP_HEAD_QUANT.md` | 08-15 |
| KLD-vs-BF16 charts are **structurally blind** to the draft head; it never runs in a normal forward pass | `qwen38-packagers/RESULT_AD_LADDER_HEAD_AUDIT.md` | 08-15 |
| Speculation multiplies throughput **variance ~8x** (off arms 2-7% spread, on arms 40-58%) | `qwen38-splitmode/RESULT_SPLIT_X_MTP.md` | 08-15 |

## split modes · multi-GPU

| finding | receipt | date |
|---|---|---|
| `-sm tensor` is **1.62x over one P100**; `-sm layer` across two is **inert** (and bit-identical to single) | `qwen38-splitmode/RESULT_P100_SM_TENSOR.md` | 08-14 |
| Split mode and MTP **compose multiplicatively** — 2.433x measured vs 2.432x predicted | `qwen38-splitmode/RESULT_SPLIT_X_MTP.md` | 08-15 |
| `--numa distribute` is worth **+13.6%** warm decode but makes cold first-response ~2x worse | `battle16gb/DS4_REBASELINE_NUMA.md` | 08-02 |

## KV cache · quantisation fidelity

| finding | receipt | date |
|---|---|---|
| q8_0 KV is the **gentlest codec measured and depth-invariant** (98.7% same-top at every ctx) | `hermesagent20/KV_KLD_PANEL.md` | 07-28 |
| Perplexity panels **cannot settle generation-path questions** — teacher-forced != decode | `hermesagent20/KV_QUANT_GENERATION_EFFECT.md` | 07-28 |
| `-fa on` costs **more fidelity than BF16->Q8_0**, and perplexity cannot see it | `battle16gb/FA_EQUIVALENCE_SM60.md` | 07-30 |
| TurboQuant weights **lose to k-quants** on fidelity-per-bit | `pulsar/PHASE1_TQ_FIDELITY_RESULTS.md` | 08-04 |
| The quant label is **not a spec** — three publishers' `Q4_K_M` span 2 GB and ~2x KLD | `qwen38-packagers/RESULT_AD_LADDER_HEAD_AUDIT.md` | 08-15 |

## hardware-specific

| finding | receipt | date |
|---|---|---|
| sm_60 FAST_FP16 carve-out — median KLD 0.0023 -> 0.000001, same-top 96.5 -> 99.9% | `mtp-sm60/SUMMARY.md` | — |
| Pascal `mul_mat_id` guard costs **~50% of all MoE throughput** on sm_60, and sm_60 doesn't reproduce the bug it guards | `pulsar/PASCAL_MMID_GUARD_COST.md` | 08-03 |
| Pascal decode at 150W is **compute-bound, not bandwidth-bound** (24% of HBM2 peak) | `qwen38-splitmode/NOTE_PRECISION_VS_SPECULATION.md` | 08-15 |
| turbo3 V-cache corruption is **Polaris-specific**; root cause wave64 subgroup ballot packing | `battle16gb/TURBO3_241_WAVE64_FIX_CONFIRMED.md` | 07-31 |
| MoE expert cache on 4xP100 **engages and makes it 2.6-3.8x SLOWER** | `rdna4-moe-cache/RESULT_DEEPSEEK_V4_P100.md` | 08-14 |
| RDNA4 VGPR spills too, worse, and not only at head size 256 | `rdna4-vgpr-spill/RESULT_GFX1201.md` | 08-14 |

## instrument validity — read before designing a benchmark

| finding | receipt | date |
|---|---|---|
| **All four cells 8/8. The instrument saturated.** Zero discriminating power | `qwen38-lowbit/RESULT_2x2.md` | 08-14 |
| Prompt-cache test was **underpowered for the question it asked** | `battle16gb/DS4_PROMPTCACHE_INCONCLUSIVE.md` | 08-01 |
| A published decode rate was a **cold-cache artifact** — warm steady state 2.2x higher | `battle16gb/DS4_DECODE_WARMUP.md` | 08-02 |
| Both headline findings were **a stale wheel**, and that is the finding | `rdna4-gemm-dtype/RESULT_GEMM_DTYPE.md` | 08-09 |
| HLE quant-delta use **withdrawn** — McNemar needs ~10 discordant pairs; a 5% base rate yields 1-6 | `hle-mini/POWER.md` | 08-15 |
| Head-isolation acceptance result recorded **UNRESOLVED** — within-arm swing 5.4pp vs 1.86pp effect | `qwen38-packagers/RESULT_AD_LADDER_HEAD_AUDIT.md` | 08-15 |

## which binary produced this

Three forks are in use and they are **not interchangeable**. Every receipt should name one.

| node | fork | note |
|---|---|---|
| `.73` | `spiritbuun/buun-llama-cpp` | `a8e5b5a38`, **805 commits ahead** of upstream b9637 |
| control plane | `giveen/llama-cpp-turboquant` (`moe-cache-test`) | `bb3c3fa` |
| `.73` `llama_stock_ref` | **NOT stock** — carries laguna patches | `adeff9b82` |

There is currently **no true upstream reference binary on either box**, so "does this reproduce
on stock llama.cpp" cannot be answered without building one. `DETERMINISM_ROOT_CAUSE.md` did
test genuine upstream `0e4a03622` on 2026-07-27; that checkout may still exist.
