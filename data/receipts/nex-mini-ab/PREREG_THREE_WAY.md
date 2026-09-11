# Pre-registration — three finetunes of one 35B-A3B shape on HumanEval+

**Logged 2026-09-11, before any model was downloaded to the test box and before any run.**

## Why

Mark's claim: Nex-N2.5-mini is "about the same speed as Qwen3.6-35B-A3B and significantly smarter",
which would make it a win for people on older cards. He then added Ornith-1.5-35B-A3B, the other
popular finetune aimed at the same audience. So there are two questions:
- **Does a finetune beat its stock base?**
- **Which of the two finetunes is better?**

## Models — one shape, three weights

Every field in the three `config.json` files matches:
- `qwen3_5_moe`, 40 layers, hidden 2048
- 256 experts with 8 active, plus a shared expert of 512
- 16 query heads, 2 KV heads, head_dim 256
- 3 linear-attention layers to every full one
- 262k context
- a one-layer MTP head

All three files are bartowski Q4_K_M, pinned by hash:

| arm | file | bytes | sha256 | repo commit |
|---|---|---|---|---|
| NEX | `nex-agi_Nex-N2.5-mini-Q4_K_M.gguf` | 22,318,512,256 | `7f4b8e921dd000e7232c48f53a67a022da22914a52f9fdf972cbdab6f9c407ef` | `0048da1a` |
| QWEN | `Qwen_Qwen3.6-35B-A3B-Q4_K_M.gguf` | 22,285,080,192 | `b46fedd33e0bfb0cae308aa3c158d0a4b2c4a1d2185a1ed6f093cdaf39064772` | `5c2410d7` |
| ORNITH | `Ornith-1.5-35B-A3B-Q4_K_M.gguf` | 21,864,081,056 | `12d8d5c01bae7f23ea4822b2f96ba069d531f827d02a57c31002f2f95e72614a` | `64b0493d` |

## Sampling — each exactly as its own card says, for this workload

The cards are saved verbatim in `cards/`. Every value below is sent on every request (`HEP_*`
environment variables). `min_p` is pinned to 0 because llama-server's own default (0.05) is an
engine choice that no card asks for.

| arm | temp | top_p | top_k | min_p | presence | repeat | thinking |
|---|---|---|---|---|---|---|---|
| NEX | 0.7 | 0.95 | 40 | 0 | 0 | 1.0 | template default `reasoning_effort` "medium" (the model decides whether to think) |
| QWEN | 0.6 | 0.95 | 20 | 0 | 0 | 1.0 | on (default); the card's "thinking mode for precise coding" profile |
| ORNITH | 0.6 | 0.95 | 20 | 0 | 0 | 1.0 | on (default); the card's "general tasks" profile |

**Declared, not controlled:** the sampling differences and the thinking difference (NEX adaptive,
the others always on). The comparison answers "which is better when run the way its makers tell
you". Our July receipt found temperature 0.6 vs 0.7 nearly inert on HumanEval+ (88.21% vs 88.01%).
top_k 40 vs 20 is untested.

## Harness, engine, hardware

- **Harness:** `hep_eval.py`, sha `65260e72…`, identical on `.194` and in `../humaneval-plus/`.
  - 164 problems, **K = 3** completions per problem
  - `max_tokens` 16,000
  - one request in flight
  - a grader preflight before any inference
- **Buckets:** PASS / WRONG / TRUNCATED / NO_ANSWER. A completion that hits 16k is TRUNCATED; that is
  a practical failure and is reported as its own bucket.
- **Engine:** `buun-llama-cpp` `3823c9eb6` (build 11804, `~/buun-llama-cpp/build_sm60_head`, built
  2026-09-03 for sm_60). Its source contains the sm_60 FAST_FP16 carve-out
  (`fast_fp16_hardware_available` excludes compute capability 600). The same binary serves every arm.
- **Server, per arm:** 2 GPUs, `-ngl 99 -sm layer -ts 1,1 -c 32768 -np 1 -fa on --jinja`, f16 KV,
  **no speculative decoding** (all three carry an MTP head; none is used). The process is pinned to
  the socket that owns its GPUs, and each arm gets a fresh server.
- **Box:** `.194`, 4× P100 (sm_60), 150 W cap, application clocks pinned at 1063 MHz. Checked
  2026-09-11 before launch, and recorded again at each launch.

## Design — two rounds, concurrent pairs, linked through NEX

| round | GPUs 0,1 (socket 0) | GPUs 2,3 (socket 1) |
|---|---|---|
| R1 | NEX | QWEN |
| R2 | ORNITH | NEX |

- **Both direct comparisons run concurrently on the same box:** NEX–QWEN in R1, NEX–ORNITH in R2.
  QWEN–ORNITH is indirect, through NEX.
- **NEX switches socket between rounds,** so slot and model are not confounded, and its two runs
  measure round-to-round drift.
- **Concurrency costs nothing:** `.194` has already been measured running two 2-GPU jobs at once
  (13.00 vs 13.03 t/s, `splitscale/RESULT_2V4.md`).

## Metrics and analysis (fixed now)

**Accuracy.**
- pass@1, pooled over 164 × 3, plus the per-sweep mean ± sd.
- **Paired test:** compare per-problem pass counts (0–3). Count the problems where A beats B and where
  B beats A, and apply an exact two-sided sign test to those counts.

**Tokens.**
- `completion_tokens` per completion (reasoning included), with the median per arm.
- **Paired test:** per-problem mean tokens, A vs B, sign test.

**Speed.** Server-side decode rate from each completion's `eval time` line, with the median per arm.

**Power, stated plainly.** Near the ceiling few problems differ. All-one-way needs at least 6
discordant problems for p < 0.05. **Differences under about 3 points are not expected to be
distinguishable,** and will be reported as such.

**Stopping.** An arm that has not finished its 492 completions within 12 hours is stopped, and its
round is reported incomplete.

## Predictions

| id | prediction | conf |
|---|---|---|
| P-T1 | NEX pass@1 > QWEN pass@1 (R1) | 60% |
| P-T2 | ORNITH pass@1 > QWEN pass@1 (indirect, through NEX) | 60% |
| P-T3 | NEX and ORNITH within 3 points of each other (R2) | 55% |
| P-T4 | NEX uses fewer completion tokens per problem than QWEN (median, R1) | 70% |
| P-T5 | ORNITH has more TRUNCATED completions than NEX (R2) — the 9B looped at this card profile | 55% |
| P-T6 | median decode speed of NEX within 5% of QWEN (R1) and of ORNITH (R2) | 85% |
| P-T7 | NEX's pass@1 in R1 and R2 within 3 points | 75% |

## What will not be claimed

- **Nothing about agentic ability.** HumanEval+ is single-function Python.
- **Nothing about other quants,** other packagers, or other boxes.
- **Nothing about "smarter" in general.**
