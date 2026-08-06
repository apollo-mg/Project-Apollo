# DeepSeek-V4-Flash (284B) runs coherently on four 2016 Tesla P100s — at 2.16 t/s, and the ceiling is a single 20 GB tensor

`.194`, 4× Tesla P100-PCIE-16GB (sm_60, 16,269 MiB each = 63.5 GiB), 2× Xeon E5-2650 v3,
60 GiB DDR4-2133 ECC, **1063 MHz / 150 W** standing config (405 MHz at idle).
Model: `unsloth/DeepSeek-V4-Flash-0731-GGUF` **UD-IQ1_S**, 3 shards, **82.5 GB**
(5.2 MB + 49.1 GB + 33.4 GB; shard 1 is metadata — verified against `content-length`).
Build: `TheTom/llama-cpp-turboquant` @ `8a891f4b5`, CUDA, `CMAKE_CUDA_ARCHITECTURES=60`,
runtime reports `ARCHS = 600`. Date 2026-08-01.
Predictions: `PREDICTIONS_ds4_flash_p100.md`.

**Every row of HuggingFace's own compatibility widget marks this model incompatible with a
16 GB card. It loads and generates coherent text on four of them.**

## Headline

| | |
|---|---|
| load time | **3 min 12 s** |
| working config | `-ngl 99 -sm layer -ts 3,4,4,1 -fit off -fa on **-ncmoe 40**` |
| decode | **2.16 t/s** |
| prompt eval | 2.09 t/s (478 ms/token) |
| gzip ratio | **0.4689 / 0.5074 / 0.5666** — healthy band |
| CJK leakage | 0 |

Sample output, verbatim, temp 0:

> *"A dense model activates all parameters for every token, whereas a mixture-of-experts (MoE)
> model only routes each token to a small subset of its experts, leavin…"*

Factually correct, on topic, no degeneration. For scale: corrupt turbo3 output measured
0.175–0.347 gzip today; the healthy f16 control was 0.5097.

## Prediction scoring — 4 of 4

| id | claim | conf | outcome |
|---|---|---|---|
| P-D1 | loads with `-ncmoe` | 0.55 | **CONFIRMED** |
| P-D2 | coherent (gzip within 0.15 of control) | **0.45** | **CONFIRMED** — 0.469–0.567 |
| P-D3 | decode 1–6 t/s | 0.60 | **CONFIRMED** — 2.16 |
| P-D5 | `-ncmoe` required | 0.95 | **CONFIRMED** |

P-D2 was the one I expected to fail. Today's Puzzle ladder measured Q2_K leaking control on
**21.1 %** of samples where IQ4 leaked 0.0 %; IQ1_S is ~1.6 bpw, far below Q2_K. It held
anyway. Sparsity plausibly protects it — only ~8 of 256 experts fire per token, so quantisation
error does not accumulate across the full parameter count the way it does in a dense model.

## The ceiling is a single tensor, not a distribution problem

`-ncmoe 40` is a **hard floor** on 16 GB cards. Measured VRAM per device:

| config | dev0 | dev1 | dev2 | dev3 | decode |
|---|---|---|---|---|---|
| `-ncmoe 50 -ts 1,1,1,1` | 3491 | 2063 | 2091 | 2213 | 1.97 t/s |
| `-ncmoe 40 -ts 1,1,1,1` | 3491 | 2063 | 2091 | **7525** | 2.13 t/s |
| **`-ncmoe 40 -ts 3,4,4,1`** | 3491 | 2641 | 4507 | 4529 | **2.16 t/s** |
| `-ncmoe 30` (any `-ts`) | — | — | **OOM 20,587 MiB** | — | — |
| `-ncmoe 20` | — | — | **OOM 28,251 MiB** | — | — |
| `-ncmoe 10` | — | **OOM 27,613 MiB** | — | — | — |

**Rebalancing `-ts` fixed the imbalance and bought nothing.** `1,1,1,1` put 49.6 % of resident
weights on device 3; `3,4,4,1` evened it to roughly `[23 %, 17 %, 30 %, 30 %]`. Decode moved
**2.13 → 2.16 t/s**.

The reason is in the OOM sizes: taking one more layer off CPU demands **20.6 GB**, then
**28.3 GB**, *on a single device*, and the requesting device changes with `-ts` while the
size does not. **A single DS4 layer's expert tensors exceed a 16 GB card and cannot be split
across devices.** No tensor-split value fixes that.

**My hypothesis that ~50 GB of idle VRAM was exploitable was wrong.** The idle VRAM is real
and unusable at this granularity.

## `-sm tensor` and `-sm row` both fail on DS4 — and both are BUGS, not capacity limits

The 20 GB conclusion above assumes layer-split is the only option. It is not: `-sm row` splits
weights by rows and `-sm tensor` splits weights **and KV**, either of which would shard a
20 GB tensor across four cards. Both were tested. Both fail at **load time, before allocation**.

| mode | `-ncmoe` | result |
|---|---|---|
| `tensor` | 40, 30, 20, 10 | **`GGML_ASSERT(!suffix_fallback.empty())`** — `llama-model.cpp:416`, all four |
| `row` | 40 | **`pre-allocated tensor (blk.0.attn_output_a.weight (reshaped)) in a buf`** — `ggml-backend.cpp:898` |
| `row` | 30 | OOM 16,657 MiB on device 3 (got further; genuinely capacity-bound) |
| `layer` | 40 | **works** — the only working configuration |

**`-sm tensor` fails identically at every offload level**, including `-ncmoe 40`, which loads
fine under `-sm layer`. Capacity is not the variable; the assert fires during tensor-name
resolution when tensor-split meets CPU-MoE overrides.

**`-sm row` fails on `blk.0.attn_output_a.weight (reshaped)`** — a DS4-specific tensor name.
Row-split does not handle this architecture's reshaped attention weights.

Note that `-sm tensor` is **proven working on sm_60** — the `.73` HA-20 six-arm campaign ran it
throughout, and buun's `fa8b372e7` tensor-split fix was confirmed on Pascal there. So this is
DS4-specific, not a Pascal limitation. CLAUDE.md's "P100s crash with row-splitting" note is
about `row`; it does not extend to `tensor`.

**Consequence for the 20 GB claim: it is UNPROVEN.** No working alternative split exists to
test it against. What is established is narrower — *under layer-split*, one layer's expert
tensors exceed a 16 GB card. Whether a working row/tensor split would shard them is unknown,
because neither mode loads.

## `--fit on` does not solve this either

`-ngl 99 -fit on` (no `-ncmoe`) **failed**: `allocating 20255.86 MiB on device 0`. The same
~20 GB indivisible tensor. So llama.cpp's own fitter has no more room to work with than a
hand-tuned split — this is a *capacity* wall, not a planning failure, and the flag should not
be expected to route around it.

Recorded because `-fit on` is the natural first reach for exactly this situation.

## Cross-check: JabbaTheDuck reports 17.96 t/s on the same model

Reported in Discord 2026-08-01, `antirez/deepseek-v4-gguf` **IQ2_XXS** with Q8 attention,
shared-expert projections and output tensors, on a rebased-tq branch:
`-c 262144 -ngl auto --fit on -fa on -b 4096 -ub 4096`, **17.96 t/s decode, 24.09 t/s prefill**.

| | Jabba | this fleet |
|---|---|---|
| quant | IQ2_XXS mixed (Q8 attn/shexp/out) | UD-IQ1_S |
| CPU offload | **none** — `-ngl auto --fit on` works | **`-ncmoe 40` required** |
| decode | **17.96 t/s** | 2.16 t/s |

**~8× and almost all of it is CPU offload, not GPU capability.** His hardware holds the model
without offloading; every token here pays DDR4-2133 expert reads across the PCIe bus. That
`-ngl auto --fit on` succeeds for him and OOMs here on the identical flag is the cleanest
evidence that our wall is 16 GB cards vs ~20 GB layer tensors.

His mixed-precision quant is the untested lever — protect attention/shared-expert/output at
Q8, push routed experts to IQ2_XXS. Unlikely to help *this* fleet (it is larger than IQ1_S, so
offload would worsen), but it is the right shape for hardware that can hold the model.

Third-party quality signal, his: the same build scored **B+ on a snake-game task from Gemini
Pro 3.1, ChatGPT and DeepSeek Pro independently**. Not our measurement, but consistent with
the coherence result here.

## CORRECTION 2026-08-02 (b) — the 2.16 t/s decode headline is a COLD-CACHE artifact

Every decode figure in this receipt is the **first generation of a fresh server process**.
`ds4_ts_tune.sh` loads a new server per configuration and generates exactly once, so 2.16 t/s
(and the 2.13 in the sweep) measure a cold page cache. With `-ncmoe 40` the routed experts are
read from CPU memory on every token, and the first generation faults them in from disk.

Measured across three identical draws in one process (`DS4_DECODE_WARMUP.md`):
**1.74 → 4.21 → 4.75 t/s**, output byte-stable throughout.

**Corrected: ~1.7–1.8 t/s cold, ~4.2–4.8 t/s warm.** The table below and the "at 2.16 t/s a
400-token answer takes ~3 minutes" read are the *cold* case; warm, that answer is ~85 s. Quote
the cold figure for first-response latency and the warm figure for sustained use — never one
number without saying which.

## CORRECTION 2026-08-02 — the prefill figure below is pessimistic by ~6×, and the verdict flips

The "478 ms/token" prefill rate and the "~32 minutes for a 4k context" conclusion in
*Practical read* are **wrong**, measured on a ~30-token prompt where fixed per-request
overhead dominates and a per-token rate is meaningless.

Measured at real depth (`DS4_PROMPTCACHE_LONGCTX.md`): **61–83 ms/token at ~8k tokens.** An
8k-token document ingests in **~10 minutes, not ~64**.

More importantly, **prompt caching removes the repeat prefill cost**: uncached, every
follow-up on an 8k context re-prefills ~8,000 tokens for **~8.5 minutes**; cached, it
prefills only the delta. That penalty disappears, leaving turns **decode-bound at roughly
2–3 minutes** — an estimated ~3.7× per-turn improvement, not the 16× the raw measurement
first suggested (that run failed to feed assistant replies back, so its cached turns were
unrealistically cheap — see the DEFECT section of `DS4_PROMPTCACHE_LONGCTX.md`).

So the "research companion, not an agent backend" framing below is **directionally right but
too harsh** on the chat case: paste a document once (~10 min), then converse at minutes per
turn. Two caveats: `-c 8192` barely holds an 8k document plus one real reply before eviction,
and agent use now looks *harder*, since tool results mutate and grow context — the two things
that break prefix reuse.

## Practical read

For a 4×P100 fleet, DS4-Flash IQ1_S is a **research-companion / long-form chat** model, not an
agent backend. At 2.16 t/s a 400-token answer takes ~3 minutes. Prefill at 478 ms/token means
a 4k-token context costs ~32 minutes before the first output token, so long-context use is
impractical without a prompt cache.

The finding is that it *runs at all*, coherently, on hardware every compatibility table
excludes.

## Limits

- **K=1, two prompts, 200–400 tokens.** A load probe, not a benchmark. No capability claim.
- gzip ratio detects **degeneration**, not correctness. "Not degenerate" ≠ "good at 1.6 bpw."
- One quant. IQ1_M (86.9 GB) and everything above do not fit; there is no ladder here.
- Decode rate is a property of *this box* (DDR4-2133, dual E5-2650 v3), not of the model —
  see Jabba's 17.96 t/s on the same architecture.
- The 20 GB indivisible tensor is inferred from OOM request sizes across five configurations,
  not read from GGUF metadata. Reading the tensor table directly would confirm it.
- **The 20 GB wall is unproven as a hard limit** — both alternative split modes fail with
  load-time asserts, so no configuration exists that could shard those tensors. If either bug
  is fixed, the ceiling must be re-measured.
- `-ncmoe 40` was found by a coarse ladder (50/40/30). Values between 41 and 49 were never
  tested and one of them may be faster.

## Provenance

- `.194:~/ds4_probe/` (load probe), `~/ds4_sweep/` (`-ncmoe` ladder), `~/ds4_ts/` (`-ts` rebalance)
- Scripts: `~/ds4_probe.sh`, `~/ds4_sweep.sh`, `~/ds4_ts_tune.sh`; local copies in `scratchpad/`
- Build: `~/llama_tq_ds4/build_ds4` @ `8a891f4b5`; sm_60 FAST_FP16 carve-out already present
  upstream in Tom's fork (`common.cuh:261`), no local patch needed
- Disk freed for this: Qwen3.6-27B BF16 pair + Darwin-28B-REASON (75.9 GB), both re-downloadable
