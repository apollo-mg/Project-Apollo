# DS4 re-baseline: `--numa distribute` is worth **+13.6%** on warm decode, not +22.7% — and it makes cold first-response ~2× worse

`.194`, 4× Tesla P100-PCIE-16GB, **1063 MHz**, ~31 W/card under load (GPUs idle at 6.5% util).
DS4-Flash UD-IQ1_S 82.5 GB, build `331981025`,
`-c 8192 -ngl 99 -sm layer -ts 3,4,4,1 -fit off -fa on -ncmoe 40`. Date 2026-08-02.
Arms: **distribute → none → distribute**, page cache dropped before each, VRAM identical
(`3491 2641 4507 4529` MiB) in all three.

## Headline

| arm | COLD (draw 1) | WARM 200-tok | spread | 226-tok gen | prefill (3989 tok) |
|---|---|---|---|---|---|
| dist_a | **1.13** t/s | **5.31** t/s | 0.8% | 4.57 t/s | 132.15 ms/tok |
| nonuma | **2.30** t/s | **4.61** t/s | 1.5% | 4.37 t/s | 68.11 ms/tok |
| dist_b | **1.13** t/s | **5.16** t/s | 1.0% | 4.46 t/s | 79.82 ms/tok |

Output byte-stable everywhere — **gzip 0.4743 on every draw of every arm**.

## 1. The +22.7% figure was too high. It is +13.6%.

`DS4_NUMA_DISTRIBUTE.md` published **4.58 → 5.62 t/s (+22.7%)** from K=1 per policy. Re-measured:

- **The control reproduces.** nonuma 4.61 here vs 4.58 there — 0.7% apart.
- **The treatment does not.** distribute 5.31 and 5.16 here vs **5.62** there — the original run
  sat 6–9% above both repeats.

Corrected: distribute mean **5.24 t/s** vs nonuma **4.61 t/s** = **+13.6%**.

The pre-registered drift rule passes cleanly, so the effect itself is real and resolvable:

```
|dist_a − dist_b| = 0.15   <   |nonuma − dist_b| = 0.55   <   |nonuma − dist_a| = 0.70
```

**What went wrong the first time** is exactly the limitation that receipt admitted to and this run
was built to test: within-arm spread (0.5–0.8%) describes stability *inside one server process*,
and says nothing about reproducibility of the whole load-and-measure cycle. Across three
independent loads, distribute spans **5.16–5.62 t/s (~9%)** — an order of magnitude wider than
the within-arm figure that made the original result look precise.

## 2. New finding: distribute is ~2× worse cold

| | cold first draw |
|---|---|
| distribute | **1.13, 1.13** t/s |
| no policy | **2.30** t/s |

Both distribute arms landed on **1.13 t/s to the hundredth** — this is not noise. Spreading
pages and threads across both sockets appears to cost roughly a factor of two on the first
generation off a dropped cache, while paying back ~14% once warm.

So the flag is a **trade**, not a free win: it helps sustained throughput and hurts
first-response latency.

## 3. Prefill and long-generation: unresolvable, and both point the wrong way for distribute

Applying the same pre-registered rule:

- **Prefill** — `|dist_a − dist_b| = 52.3 ms/tok` vs `|nonuma − dist_b| = 11.7`. The two
  identically-configured arms differ **4.5× more** from each other than from the control.
  **VOID.** All that can be said is that both distribute arms were slower than nonuma
  (132.2 and 79.8 vs 68.1 ms/tok) and prefill is wildly unstable at K=1.
- **226-token generation** — `|dist_a − dist_b| = 0.11` vs `|nonuma − dist_b| = 0.09`. **VOID**
  by the same rule, and at this scale the rule is being applied correctly rather than
  pedantically: the candidate effect (~3%) is the same size as the disagreement between
  replicates.

Worth noting the 226-token draws are **4.37–4.57 t/s across all arms, below every arm's warm
200-token figure (4.61–5.31)** despite running after nine warming draws. Whether that is KV
growth or something else is not established here.

## 4. Consequence: the "adopt as standard" recommendation needs qualifying

`DS4_NUMA_DISTRIBUTE.md` recommended adopting `--numa distribute` for all DS4 work on this node.
That was based on the decode number alone. With the fuller picture:

| workload | verdict |
|---|---|
| sustained generation, warm cache, short prompts | **use it** — +13.6%, well-resolved |
| first-response / interactive latency | **avoid** — ~2× worse cold, highly reproducible |
| long prompts (prefill-dominated) | **unknown, possibly worse** — unresolved, both arms slower |

For benchmark batteries that load once and generate many times, it wins. For anything measuring
TTFT or dominated by prompt processing, it is at best unproven and at worst a regression.

## Ruled out as a confound on the prefill figures: the CUDA 13.2 `DeviceTopK` cliff

A report on r/LocalLLaMA (2026-08-02, u/fragment_me, diagnosis credited to u/fairydreaming)
describes a large DS4-Flash prefill regression on CUDA ≥ 13.2: *"Starting with 13.2 DeviceTopK is
used for top-k instead of argsort, this turns PP rate to crap."* Since prefill is exactly what
this receipt leaves unresolved, it had to be checked.

**Not applicable to these measurements.** The fork gates the path at `ggml-cuda/top-k.cu:6`:

```cpp
#ifdef GGML_CUDA_USE_CUB
#    include <cub/cub.cuh>
#    if (CCCL_MAJOR_VERSION >= 3 && CCCL_MINOR_VERSION >= 2)
#        define CUB_TOP_K_AVAILABLE          // -> DeviceTopK::MaxPairs
#    endif
#endif
```

`.194` builds against **`CUB_VERSION 200500`** (CCCL 2.5, CUDA 12.4) — far below the 3.2
threshold — so `CUB_TOP_K_AVAILABLE` is never defined and top-k falls through to the argsort
path (`top-k.cu:39-49, 73-98`), which is the *fast* branch in the report's framing. The
prefill numbers above are therefore not contaminated by this.

**The slow prefill here has a different and already-established cause:** with `-ncmoe 40`, 40
layers of routed experts are CPU-resident, so prefill runs them on two Haswell-EP sockets for
every token. Consistent with 6.5% GPU utilisation and ~31 W/card against a 150 W cap.

**Not reproducible on this fleet, and won't be.** CUDA 13 dropped Pascal (sm_60), so `.194`
cannot install a toolkit new enough to exhibit the regression. The 1660 Ti (sm_75) is new enough
but has 6 GB, which cannot hold an 82.5 GB model. This is a **source-verified exclusion, not a
measured one** — the claim here is only that our build cannot take the `DeviceTopK` branch, not
that the branch is or isn't slow.

**Scope note for the fork:** `top-k.cu` is near-identical to upstream `0fcb3760b` (differences
are `CUDA_CHECK` wrapping and argsort chunking), so `llama-cpp-turboquant` inherits this gate.
Any build of it with CUDA ≥ 13.2 takes `DeviceTopK`.

## Limits

- Prefill and long-generation are **K=1 per arm** and formally void. Resolving them needs the
  same repeat treatment the decode figure just got.
- The 400-token length-independence check **did not run as designed**: the request stopped at
  **226 tokens** on a stop token, so the parser's `n == 400` match found nothing. The 226-token
  rows were recovered from the server logs afterwards. Length-independence is therefore still
  untested at 400.
- One model, one config, one machine. Cold figures are specific to a fully dropped page cache.
- `distribute` vs `interleave` remains unexplained (interleave was not re-run here; it measured
  4.89 t/s previously, also K=1, and should be treated as provisional).
- Load times 138–186 s across arms with no evident pattern.

## Provenance

- `.194:~/ds4_rebase/` — `rebase.log`, `server_{dist_a,nonuma,dist_b}.log`, `r_*.json` responses
- Script `scratchpad/ds4_rebase.sh`
- Supersedes the headline figures in `DS4_NUMA_DISTRIBUTE.md` (correction block added there)
- Cold/warm distinction and the warming curve: `DS4_DECODE_WARMUP.md`
