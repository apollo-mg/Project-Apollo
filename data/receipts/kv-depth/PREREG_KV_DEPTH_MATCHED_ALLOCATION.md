# Pre-registration — KV codecs at depth, matched on VRAM allocation, VBR included

**2026-09-23, written before any fidelity arm ran.** Desktop RX 9070 XT (gfx1201, ROCm),
buun `38ada0e1b` `build_rocm` (`llama-perplexity` rebuilt at that commit today; the binary
in the tree was from 07-17 and segfaulted on `--version`).

## Why this exists

ggml-org/llama.cpp#20977 ("TurboQuant support") was closed NOT_PLANNED on 2026-08-20. The
argument in the thread: the gain over the existing `q4_0` KV is "miniscule", the codecs are
slow, and the maintenance isn't worth it. Mark's position: **VBR matters more than the turbo
codecs**, because a static quantized cache pays its quality tax on every token for capacity
you may never use, while VBR starts at f16 and degrades only under pressure.

Nobody in that thread measured the comparison that decides it: **fidelity across depth at a
fixed KV VRAM allocation.** Our own ledger cannot answer it either (see prior art).

## Conflict of interest

Mark collaborates with buun, VBR's author. The method, the arms, and the losing outcomes are
fixed here before data exists.

**Prior art checked:** `ledger_precheck.py "turbo KV cache codec vs q8_0 q4_0 quality VRAM context"`,
`"VBR variable bit rate KV fidelity bytes per token context capacity"`, and
`"asymmetric K V cache types matched bytes VBR vs q4_0 decode speed consumer" --deep`
-> receipts found:
- `kv-fidelity/RESULT_U5_FIDELITY.md` (turbo4 R 68.1 < q4_0 89.5, Tom's fork, 9B, 9070) and
  `RESULT_U5B_BUUN.md` (**reversed**: q4_0 22.1 < turbo4 32.2, buun, 27B, P100). The
  turbo4-vs-q4_0 ranking is not robust.
- `RESULT_U5CD_PLACEMENT.md` / `RESULT_U5F_ALLOCATION.md`: at equal cost the bits belong on
  **V** (31.7-37.7 %).
- `RESULT_U5G_MIXED_KV_IS_SLOW.md`: mixed K/V ~27x slower at 16k on P100.
- `SCOPE_CORRECTION_136_TOKENS.md`: **every number above is a 136-token cache.**
- `NOTE_VBR_IS_PATH_DEPENDENT.md`: `frontier-hazard` cannot reach VBR at all.
- `vbr-fidelity/RESULT_VBR_FIDELITY.md`: VBR at 3.25 bpv matched f16 on 24-item calibration
  (sensitivity floor stated); VBR did not beat static CBR at matched bytes (G2 failed).
- `viability/RESULT_SPEED_AAD85.md`: on the 9070, VBR decode is within ±0.5 % of f16 at 13k.

**What this adds:** (1) depth, positions 16,384-32,767 instead of < 136; (2) VBR measured by
the same instrument as the static codecs; (3) the U5f K-vs-V allocation replicated at depth;
(4) the allocation-matched framing a consumer actually faces ("I have X MiB for KV").

## Feasibility gates (run 2026-09-23 before this file; plumbing only)

Single 4,096-token chunks, plain PPL, no KLD, logs in the scratchpad. **Disclosure:** the gate
logs printed single-chunk 4k PPLs (q8_0 8.2896, q4_0 8.3260, q4_0-K/q8_0-V 8.2929,
q8_0-K/q4_0-V 8.3043, VBR 16 MiB 8.7696). These are one chunk, at 4k, not KLD, and not the
depth window. They are disclosed here, not used.

1. **VBR reaches `llama-perplexity`.** `-ctk vbr -ctv vbr --vbr-vram 16M` logs `entry tier f16`,
   73 degrades to `turbo1_tcq`. **Degrades are pre-emptive per batch**: the controller projects
   the incoming batch and degrades before it lands (`projected 16.00 / budget 16.00 MiB at
   2048 cells` then 73 degrades inside 0.6 s). Batch size is therefore the resolution of the
   fidelity-vs-fill curve, and it must be identical across the base and every arm.
2. **Tiers reset per chunk.** `VBR full reset: cache empty — 16 tensors back at their entry
   tier`. Each chunk is an independent fill.
3. **Per-position KLD is available.** `TURBO_KLD_DUMP=<file>` writes
   `[int32 n_pos][int32 n_chunk][float32 kld[n_chunk*n_pos]]`, chunk-major, pre-sort,
   positions `n_ctx/2 .. n_ctx-2` of each chunk (`perplexity.cpp:2121-2140`).
4. **Mixed K/V on this build converts to f16.** `no FlashAttention vector kernel compiled for
   q4_0-q8_0; converting to f16. Add the pair to GGML_CUDA_FA_QUANTS for native execution.`
   The stored values are still quantized, so fidelity is valid; speed is not representative.
   `GGML_CUDA_FA_ALL_QUANTS=OFF` in `build_rocm/CMakeCache.txt`.
5. **`--n-ubatch 8` is no longer needed** for quantized KV on gfx1201 (q4_0 at ub 512 completed).
   `U5`'s workaround is obsolete on this commit.

## Fixed setup (all arms)

- Model `Qwen_Qwen3.5-9B-Q8_0.gguf`, sha256 `b58fe056b5435070240de259f3f981aa38fee96825bbd78c088d5fd90e46f2b5`
  (arch qwen35 hybrid: **8 of 32 layers carry KV**, D=256, GQA 4:1; recurrent state is not
  quantized). Weights identical across arms, so KLD isolates the KV codec.
- Corpus `wikitext-2-raw/wiki.test.raw`, sha256 `173c87a53759e0201f33e0ccf978e510c2042d7f2cb78229d9a50d79b9e7dd08`.
- `-c 32768 -b 512 -ub 512 -ngl 99 -fa on -v`, all available full chunks (expected 8-9), one
  process per arm (`-v` is required: degrade lines are INFO-level and print only with it), `HIP_VISIBLE_DEVICES=0`, benchmark lock held.
- Reference: f16/f16 run writing `--kl-divergence-base` to `/mnt/TG_2TB/AI/kld/kvdepth/`
  (~8 GB per chunk; not committed). **Default uint16-quantized log-prob base**, not
  `LLAMA_KLD_EXACT_BASE` (which doubles size and I/O). The uint16 base has a nonzero KLD
  floor; that is why `C0` is a measured floor and H1 is a dump-vs-dump comparison. Every arm: `--kl-divergence --kl-divergence-base` plus
  `TURBO_KLD_DUMP`. The dumps (~0.5 MB each) are committed.
- f16 KV costs 32 KiB per cell on this model (measured: 128 MiB at 4,096 cells), so **1,024 MiB
  at 32,768**.

## Arms

| id | KV | allocation at 32k | purpose |
|---|---|---:|---|
| `C0` | f16 / f16 | 1,024 MiB | determinism control vs base |
| `C1` | VBR, `--vbr-vram 2048M` | never binds | "starts at f16", literal: must equal `C0` |
| `Q8` | q8_0 / q8_0 | 544 MiB | static |
| `Q4` | q4_0 / q4_0 | 288 MiB | the stock-llama.cpp alternative |
| `T4` | turbo4 / turbo4 | 264 MiB | static turbo (8 % fewer bytes than Q4; not matched, stated) |
| `T3` | turbo3_tcq / turbo3_tcq | 208 MiB | static low tier |
| `KR` | q8_0 K / q4_0 V | 416 MiB | U5f K-rich, at depth |
| `VR` | q4_0 K / q8_0 V | 416 MiB | U5f V-rich, at depth |
| `VK` | VBR, `--vbr-vram 768M` | 768 MiB | knee at ~24,576 cells, **inside** the scored window |
| `V8` | VBR, `--vbr-vram 544M` | 544 MiB | **matched to `Q8`** |
| `V4` | VBR, `--vbr-vram 288M` | 288 MiB | **matched to `Q4`** |

VBR arms use `-ctk vbr -ctv vbr`, default floor (t1 for an explicit `-ct vbr`), and the
**generic cross-model degrade order**: this build has no measured order for this
arch/n_layer. That is what a user gets by default, and it handicaps VBR relative to a
measured order. Stated, not corrected.

## Validity gates (a failure voids the named comparison, not the run)

- `C0` (f16 vs the uint16 base) is the **measurement floor**, reported, not assumed zero.
  If `C0` mean KLD is ≥ 10 % of `Q8`'s, the base quantization swamps the q8_0 comparisons
  and H2 is void.
- **Allocation match.** Static arms: the `KV buffer size` line. VBR arms: `mapped X MiB` at
  the last degrade or batch of each chunk. A matched pair (`V8`/`Q8`, `V4`/`Q4`) outside
  **±2 %** of each other voids that comparison.
- Every static arm's log shows the requested `K (type)` / `V (type)`. Every VBR arm except
  `C1` logs `VBR degrade #` lines; `C1` logs **none**.
- Each run has a `Final estimate` line and the dump reports `n_chunk` equal to the base's.
  `llama-perplexity` exits 0 on failure, so rc is not a gate.

## Predictions

Unit: per-position KLD from the dump. Paired differences use common random numbers: the
same positions in the same chunks. **Inference: exact two-sided sign-flip permutation test on
the chunk-level paired mean differences** (chunks are the independent unit; 2^n_chunk
permutations, enumerated). With 8 chunks the smallest attainable p is 2/256 = 0.0078, reached
only if every chunk agrees. α = 0.05. A percentile bootstrap CI over chunks is reported as
descriptive only, since with this few units it is anticonservative, which here would favour
VBR.

| # | claim | test | conf |
|---|---|---|---:|
| H1 | **VBR costs nothing before pressure** | per-position `VK` dump **equals** `C1` dump (same base, so the uint16 floor cancels) at every scored position before `VK`'s first degrade in that chunk. The knee is the cell count at degrade #1 per chunk, from the `projected ... at N cells` line preceding it. Pass: max abs difference ≤ 1e-6 | 0.80 |
| H2 | VBR beats static at matched allocation, q8_0 budget | `V8` mean KLD over the full window < `Q8`, permutation p < 0.05 | 0.55 |
| H3 | VBR beats static at matched allocation, q4_0 budget | `V4` mean KLD < `Q4`, permutation p < 0.05 | 0.55 |
| H4 | U5f survives depth: bits belong on V | `VR` mean KLD < `KR`, permutation p < 0.05 | 0.60 |
| H5 | q4_0's excess over q8_0 grows with depth | per-1k-bin (`Q4` − `Q8`) mean KLD has a positive slope across 16k-32k; per-chunk slopes, permutation p < 0.05. (Absolute slope is confounded by base entropy changing with position, so it is descriptive only) | 0.50 |

**Losing outcomes, named now:**
- **H1 false** means "starts at f16" does not hold in practice (for instance the sink-stash or
  the pool degrades early). That would undercut Mark's thesis at its root, and it gets
  reported first.
- **H2 or H3 false** (VBR ≥ static at matched allocation) means VBR's advantage is capacity
  and short-context quality, not quality per byte once full. That matches the prior G2
  result. The article then says "VBR is free until it isn't, and at equal VRAM when full it
  is no better than q4_0", and upstream's argument stands on that axis.
- **H4 reversed** means U5f was a shallow-cache artefact.

**`C1` vs `C0`, reported as its own finding.** VBR's f16 entry runs through the VMM pool,
the sink-stash and a turbo layout, so it may not be bit-identical to stock f16. Any difference
is reported. H1 is defined against `C1`, not `C0`, so that a pool-level difference cannot
masquerade as a degrade cost, nor a degrade cost hide inside a pool difference.

## Secondary, descriptive only

- `seconds per pass` per arm (prefill-dominated, **not decode**). The mixed arms run the f16
  conversion path, so their speed is not representative. A decode-speed leg at depth is a
  separate test.
- VBR realized tier per tensor at the end of each chunk, reconstructed from the degrade log.
- Per-1k-bin KLD curves for every arm (the figure for the article).

## Not established by this test, whatever the outcome

One model (hybrid, only 8 KV layers, so KV effects are diluted relative to a dense-attention
model), one corpus (wikitext is short articles concatenated, so long-range attention is
weak, so the claim is "positions 16k-32k", not "long-range attention"), one card, teacher-forced, not generative, and no task score. Fidelity to an f16
reference is not goodness.

## Amendment 1 — 2026-09-23 ~11:20, after C0/C1/VK ran, before any static arm ran and before any dump was read

Prompted by buun (via Mark): *"should include turbo8 for the q8_0 compare, and should also compare
bpw because the turbo types are actually smaller than their K quant equivs."* Also: the upstream
decision compared TheTom's older implementation, and buun's fork has since added an **affine
tap** (buun: -30 % KLD). This run is buun `38ada0e1b`, so it measures the current codec, not the
one upstream judged.

- **New arm `T8`**: `-ctk turbo8 -ctv turbo8`, 8.125 bpv, **520 MiB** at 32k (vs `Q8` 544). `U5b`
  compared these at 136 tokens and was underpowered (1 vs 6 events). This is the depth version.
- **New descriptive output, the bytes-vs-KLD frontier**: every arm plotted as (allocated MiB, mean
  KLD), so a codec that is smaller *and* equal is visible as a win rather than lost in a
  label-matched pair. Turbo types are the cheaper side of every label pair (turbo8 -4.4 %,
  turbo4 -8.3 % vs their q equivalents).
- **No new hypothesis test** is added for `T8` vs `Q8` or `T4` vs `Q4`. They are not
  byte-matched, so they are frontier points, not paired tests. Stated so a win or a loss cannot be
  promoted after the fact.
- **Speed framing, for the later decode leg** (not this run): buun's correction stands. VBR decodes
  at f16 speed while its tensors are f16, and the 8.61-9.07 t/s in `RESULT_VBR_FIDELITY.md` was VBR
  *already degraded to turbo3-class tiers*. The fair comparator for a ~3-4 bpv codec is `q4_0`, not
  f16.

## Amendment 2 — 2026-09-23 ~11:55, after all arms ran, before any KLD dump or KLD line except C0's was read

**Validity gate failed: `C1` logged 655 degrades** (the prereg required none). `C1` first degraded at
25,088 cells with 784.5 MiB mapped against an explicit 2,048 MiB budget. `V4` (288 MiB) logged *fewer*
degrades (279) than `V8` (656).

**Cause, from source** (`src/llama-kv-cache.cpp:4280-4310`, `vbr_budget_eff_uncached`): the explicit
budget is not the trigger. It is clamped every boundary by **live free device VRAM minus a growth
reserve** (`vbr_growth_headroom_`: fit target, else 1 GiB default, `:1838-1845`). This 9070 also drives
the desktop, and `llama-perplexity` holds a 512 x 248,320-float output buffer, so free VRAM, not the
flag, bound every VBR arm. By the prereg's own gate, **H1-H3 are void on the original VBR arms.**

**This is itself a finding, and it is reported:** on a 16 GB consumer card that is also the display
GPU, `--vbr-vram` is a ceiling, not an allocation. VBR degrades earlier than its nominal budget to
keep ~1 GiB of headroom. That is defensible production behaviour (it avoids OOM), but it means
"VBR at budget X" is not a controlled condition on such a card.

**Re-run, fixing the method only:**
- Arms `C1F`, `VKF`, `V8F`, `V4F`: identical to `C1`/`VK`/`V8`/`V4`, plus `VBR_FREEZE=1` and a matching
  `VBR_BUDGET_MIB` (source `:1798-1813`: "a fixed budget + no clamp makes degrade waves a pure function
  of occupancy", test/gating only), plus `VBR_TRACE` for per-boundary mapped bytes (the allocation gate
  and the knee).
- H1-H3 are scored on the `F` arms, with the same tests, thresholds and gates.
- The original unfrozen VBR arms are kept and reported **descriptively** as "production mode on a
  display GPU". They are not scored against any hypothesis.
- Risk, stated: freeze removes the OOM protection. If an `F` arm OOMs, that is reported, not retried
  with a smaller context.

## Amendment 3 — 2026-09-23 ~12:40, AFTER the frozen arms were scored

**The allocation gate failed for both matched pairs.** Frozen VBR mapped more than its nominal budget
(pool pages plus the f16 sink-stash): `V8F` 558.0 MiB vs `Q8` 544 (+2.6 %), `V4F` 299.0 vs `Q4` 288
(+3.8 %), both outside the ±2 % tolerance. **H2 and H3 as run are VOID.** Their effect sizes are
recorded in the result but not scored.

**Re-run, written after seeing the voided results, so it is constrained to be conservative:** arms
`V8C` and `V4C` are identical to `V8F`/`V4F`, but their budget is reduced by the observed overshoot
(`VBR_BUDGET_MIB` 530 and 277) so that mapped bytes are **≤** the static arm's allocation. A smaller
budget can only raise VBR's KLD, so this correction cannot manufacture a VBR win. Pass requires mapped
within [-2 %, 0 %] of the static arm; if that misses, H2/H3 stay void and no further tuning is done.
Same tests and thresholds.
