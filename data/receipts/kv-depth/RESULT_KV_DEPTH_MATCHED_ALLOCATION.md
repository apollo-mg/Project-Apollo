# Frozen VBR beats static q8_0 by 71 % at equal KV VRAM, and is bit-exact f16 before pressure; as shipped, VBR collapsed to its floor after the first long request

**Read both halves. They travel together.** The allocator result below was measured with `VBR_FREEZE=1`
(a test mode). The same binary on the same card, **unfrozen**, handled the first 32k chunk well
(KLD 0.0001) and then **degraded every later chunk from an empty cache to the 1.25-bpv floor**
(KLD 0.13, 60x worse than q8_0). The bridge between the halves is `V4`: unfrozen at 288 MiB, it
never hit the problem and is **bit-identical to frozen `V4F`**. When nothing sticks, production
equals frozen.

**2026-09-23**, RX 9070 XT (gfx1201, ROCm), buun `38ada0e1b` `build_rocm`, `llama-perplexity` with
`TURBO_KLD_DUMP`. `Qwen_Qwen3.5-9B-Q8_0` (sha256 `b58fe056...`; qwen35 hybrid, 8 of 32 layers carry KV,
D=256), wikitext-2 test, `-c 32768 -b 512 -ub 512 -fa on`, **9 chunks x 16,383 scored positions
(16,384-32,766)** per arm, teacher-forced, KLD against an f16-KV reference of the same weights.
Pre-registration: `PREREG_KV_DEPTH_MATCHED_ALLOCATION.md` with **three amendments, two of them forced
by failed validity gates** (below). Run log with prereg/runner hashes: `RUNLOG.txt`. Dumps, VBR traces and
gzipped logs: `raw/`. Scorer: `analyze_kvdepth.py` -> `RESULT_kvdepth.json`.

**Conflict of interest:** Mark collaborates with buun, VBR's author, and buun reviewed the framing
mid-run (Amendment 1 added his `turbo8` arm). Read the gate failures before the headline.

## Headline

| # | prediction | result |
|---|---|---|
| H1 | VBR costs nothing before pressure | **PASS, exactly.** Frozen VBR (`VKF`) is **bit-identical** to f16-entry VBR (`C1F`) on all **69,120** pre-knee positions (max abs diff 0.0). `C1F` is itself bit-identical to stock f16 (`C0`) on all 147,447 positions. |
| H2 | VBR < static q8_0 at matched allocation | **PASS.** `V8C` (543.5 MiB) mean KLD **0.000644** vs `Q8` (544.0 MiB) **0.002237**: **-71 %**, lower in **9/9 chunks**, exact permutation p = 0.0039 (the minimum attainable with 9 chunks). |
| H3 | VBR < static q4_0 at matched allocation | **VOID** (allocation gate). `V4C` mapped 289.2 MiB vs `Q4` 288.0 (+0.4 %), outside the pre-set [-2 %, 0] window, and Amendment 3 forbade further tuning. Descriptively: **-50 %** KLD, 9/9 chunks. |
| H4 | bits belong on V (U5f) | **FAIL, reversed.** V-rich `q4_0`/`q8_0` is **48 % worse** than K-rich `q8_0`/`q4_0` at equal bytes, 9/9 chunks, p = 0.0039. |
| H5 | q4_0's excess over q8_0 grows with depth | **FAIL.** Slope indistinguishable from zero (5/9 chunks positive, p = 0.99). |

## The allocation frontier (all arms, mean KLD over positions 16k-32k)

| arm | KV | allocated MiB | mean KLD | p99 KLD |
|---|---|---:|---:|---:|
| `C0` | f16 | 1024.0 | 0 | 0.00004 |
| `VKF` | VBR frozen, 768M budget | 780.5 | 0.000104 | 0.00090 |
| **`V8C`** | **VBR frozen, 530M budget** | **543.5** | **0.000644** | 0.00256 |
| `Q8` | q8_0 | 544.0 | 0.002237 | 0.00454 |
| `T8` | turbo8 | 520.1 | 0.002170 | 0.00477 |
| `KR` | q8_0 K / q4_0 V | 416.0 | 0.004454 | 0.01196 |
| `VR` | q4_0 K / q8_0 V | 416.0 | 0.006604 | 0.02064 |
| `V4C` | VBR frozen, 277M budget | 289.2 | 0.004753 | 0.01930 |
| `Q4` | q4_0 | 288.0 | 0.009482 | 0.02692 |
| `T4` | turbo4 | 264.1 | 0.008489 | 0.02978 |
| `T3` | turbo3_tcq | 208.1 | 0.015215 | 0.06157 |

Read it as a frontier, per buun's point that label pairs hide byte differences:
- **turbo8 vs q8_0:** 4.4 % fewer bytes, 3 % lower KLD. At least a tie, on less memory.
- **turbo4 vs q4_0:** 8.3 % fewer bytes, 10 % lower KLD. At depth, on buun's current build, turbo4 is
  smaller **and** better. `U5b` (136 tokens, 27B, P100, older build) had it the other way. These two are
  not byte-matched and were registered as frontier points, not tests (Amendment 1).
- **VBR at q4_0's allocation (`V4C`) roughly matches static K-rich at 416 MiB**, i.e. 44 % more memory.

## Per-depth curve (mean KLD per 1k bin, selected)

| bin start | `C1F` | `VKF` | `V8C` | `Q8` | `T8` | `V4C` | `Q4` | `T4` |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 16,384 | 0 | 0 | 0.00003 | 0.00163 | 0.00166 | 0.00069 | 0.00470 | 0.00374 |
| 22,528 | 0 | 0 | 0.00032 | 0.00376 | 0.00324 | 0.00553 | 0.00725 | 0.00765 |
| 24,576 | 0 | **0.00008** | 0.00068 | 0.00231 | 0.00214 | 0.00499 | 0.01062 | 0.00931 |
| 31,744 | 0 | 0.00033 | 0.00171 | 0.00433 | 0.00402 | 0.00890 | 0.01549 | 0.00980 |

`VKF`'s knee is at position **24,064 in every chunk** (budget 768 MiB / 32 KiB per cell = 24,576 cells,
minus the 512-token batch that triggers the pre-emptive degrade). Zero before, nonzero after.

## What the H2 win is NOT yet attributable to

**Verified:** `V8C` logged 144 degrades (16 per chunk), and all 16 tensors ended every chunk at turbo8;
`V4C` logged 288, and all 16 ended at turbo4.

**At the end of every `V8C` chunk, all 16 KV tensors have degraded to turbo8**, yet the last bin is
0.00171 against static turbo8's 0.00402. So the advantage is not only "part of the window stayed f16."
Candidates, none tested here:
- the **f16 sink-stash**: VBR keeps the first 128 rows of each (layer, side) at f16. Attention sinks are
  exactly where error is expensive.
- rows written at f16 and **transcoded later** vs quantized on arrival.
- the price-ordered degrade schedule.

The first of these could be given to a static codec.

**Also non-monotonic, and bit-deterministic, so not noise:** each trimmed arm beat its own larger-budget
version (`V8C` 0.000644 < `V8F` 0.000700; `V4C` 0.004753 < `V4F` 0.004865; `V4F` ended mixed
turbo4/turbo8, `V4C` all turbo4). Less memory gave a better cache. Together with the turbo8 gap above,
this says the 71 % belongs to **VBR's allocator as implemented** (schedule, stash, transcode path), not
to bytes alone. **The claim this receipt supports is "VBR's allocator, frozen, beats static q8_0 at
equal VRAM", not "dynamic allocation is why."** A `T8` arm with an f16
sink-stash would split it.

## Gate failures, in order (the prereg's own rules, applied)

**1. `C1` (2,048 MiB budget, "never binds") logged 655 degrades.** Amendment 2 attributed this, from
source, to the live free-VRAM clamp in `vbr_budget_eff_uncached`. **That attribution was later falsified
by measurement** (free VRAM never below 3.9 GiB in a repro; see the production section) and is left
in the prereg as written. The fix it prescribed still holds regardless of cause: `VBR_FREEZE=1` (buun's
test/gating switch, "a fixed budget + no clamp makes degrade waves a pure function of occupancy")
removes every live input, and the frozen `C1F` logged 0 degrades.

**2. Frozen VBR mapped over its nominal budget** (pool pages + sink-stash): +2.6 % and +3.8 %. H2 and
H3 voided. Amendment 3, written **after seeing those results**, re-ran with budgets trimmed by the
observed overshoot. A smaller budget can only hurt VBR, so this could not manufacture a win. H2 then
matched (-0.1 %). H3 still missed by +0.4 % and stays void by rule.

## The production-mode finding (unfrozen arms, descriptive, co-headline)

| arm | `--vbr-vram` | mean KLD | where it ended |
|---|---:|---:|---|
| `V4` | 288M | 0.004865 | turbo4/turbo8, identical to frozen `V4F` |
| `V8` | 544M | **0.132875** | **every tensor at turbo1_tcq (1.25 bpv)** |
| `VK` | 768M | **0.132857** | turbo1_tcq |
| `C1` | 2048M | **0.132855** | turbo1_tcq |

Per-chunk mean KLD, unfrozen:

| arm | chunk 1 | chunks 2-9 |
|---|---:|---|
| `C1` 2048M | **0.0001** | 0.131, 0.124, 0.163, 0.134, 0.147, 0.207, 0.141, 0.148 |
| `V8` 544M | 0.0003 | **identical to `C1` to 4 decimals** |
| `VK` 768M | 0.0001 | identical to `C1` |
| `V4` 288M | 0.0017 | 0.0046 ... 0.0103 (= `V4F`, bit-identical) |

**The collapse is state that survives the per-chunk reset, not the budget.** In chunk 1 the first
degrade came at 25,088 cells (`C1`) or 16,896 (`V8`). In **every later chunk the first degrade fired
at 0 cells**, straight after a logged `VBR full reset: cache empty — 16 tensors back at their entry
tier`, and walked all 16 tensors to `turbo1_tcq`. The first reset in `C1` reports **15** tensors,
not 16.

**The mechanism is NOT established.** A two-chunk repro (`--vbr-vram 2048M`, rocm-smi sampled every
0.5 s) reproduced it: chunk 1 first degrade at 25,088, chunk 2 at 0. But **free VRAM never fell below
3.9 GiB**, so the live free-VRAM clamp (my first hypothesis, from reading `vbr_budget_eff_uncached`)
is **not shown** to be the trigger. `VBR_FREEZE` disables the free-VRAM clamp, the co-tenancy ledger
and the grant logic together, so the frozen arms' health cannot say which of those binds. Candidates:
- the co-tenancy grant/ledger state recorded by chunk 1's degrades;
- a budget re-derivation that latches low;
- the tensor the first reset did not return.

**Scope:** observed in `llama-perplexity` only. If `llama-server` behaves the same, one long request
would leave the server's KV at the floor for every request after it. That is untested here and is
the first thing to check. Reported to buun as a reproducible observation with logs, not as a
diagnosis.

## Speed (descriptive; first-chunk prefill seconds per pass, not decode)

All arms fell between 18.9 and 24.3 s per 32k pass. The mixed arms go through a
`converting to f16` fallback on this build (`GGML_CUDA_FA_ALL_QUANTS=OFF`), but that is the vec
(decode) kernel, so prefill doesn't show it. **U5g's 27x mixed-type penalty (P100, decode at 16k)
is neither confirmed nor refuted here.** A decode-at-depth leg with `q4_0` as the comparator for
3-4 bpv codecs (buun's correction) is the next test.

## What this adds to prior art

- **The first kv-fidelity numbers at depth.** Every prior number (`U5`-`U5f`) was a 136-token cache.
- **U5f's "bits belong on V" does not survive depth on this model.** K-rich wins by 48 %. Two things
  changed at once, depth (136 -> 16k-32k) and model (27B -> 9B), so this is "U5f does not generalise",
  not yet "U5f was a depth artefact." This is the direction TheTom's asymmetric paper argued.
- **turbo4 > q4_0 at depth on current buun**, reversing `U5b`'s shallow-cache ordering.
- **VBR measured by the same instrument as static codecs** (`frontier-hazard` never could).

## Not established

- One model (hybrid; only 8 KV layers, so KV effects are diluted), one corpus (short concatenated
  articles: "positions 16k-32k", not "long-range attention"), one card, teacher-forced, no task
  score.
- VBR used the **generic cross-model degrade order** (no measured order exists for this model), which
  handicaps it.
- 9 chunks: the permutation floor is p = 0.0039, reached by H2 and H4. Effect sizes are large relative
  to chunk-to-chunk spread, but n is small.
- `VBR_FREEZE` is a test mode. The frozen results describe the allocator's quality, not production
  behaviour on a crowded card (see the table above).
