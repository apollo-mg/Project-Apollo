# On Qwen3.8-27B / Pascal, frozen VBR does not beat static KV codecs at matched allocation: it ties q8_0 at best and loses to q4_0 (-45 %) and turbo3_tcq (-89 %). The 9B/ROCm win does not generalize

**2026-09-24/25**, `.194`, one P100 per arm (1063 MHz / 150 W), buun `08826ad6e` `build_sm60_0920` `llama-perplexity`,
`-ngl 99 -fa on -c 16384 -b 512 -ub 512`, `Qwen3.8-27B-UD-Q2_K_XL`, wikitext-2 test. **18 chunks x 8,191 scored
positions** (8,192-16,382) per arm. Teacher-forced; per-position KLD against f16 KV on the same weights.
Prereg: `PREREG_VBR_RATE_DISTORTION.md` (+ Amendment 1: 32k -> 16k after an out-of-VRAM, before any arm data).
Scorer: `analyze_s4.py` -> `RESULT_s4.json`. Raw: `raw/` (dumps, VBR traces, gzipped logs with home paths redacted).

**Conflict of interest:** Mark collaborates with VBR's author, and yesterday's `kv-depth` receipt reported the
opposite result on another model. The method and the interpolation rule were fixed before the data. The headline is
unfavourable to VBR and is reported as measured.

## The curve

Allocation for static arms is the logged `KV buffer size`. For VBR it is the per-chunk maximum of `mapped_bytes`
from the trace, averaged over chunks. f16 KV at 16k = 1,024 MiB = 16 bpv.

| arm | allocation MiB | bpv equivalent | mean KLD |
|---|---:|---:|---:|
| VF (VBR, budget never binds) | -- | 16 | 0.0000000 (max 7.2e-5) |
| V75 | 814.0 | 12.72 | 0.000008 |
| V55 | 604.0 | 9.44 | 0.000176 |
| **q8_0** | 544.0 | 8.50 | **0.000425** |
| V40 | 452.0 | 7.06 | 0.003907 |
| V29 | 340.0 | 5.31 | 0.014864 |
| **q4_0** | 288.0 | 4.50 | **0.015745** |
| **turbo4** | 264.1 | 4.13 | **0.016272** |
| V22 | 264.0 | 4.12 | 0.029120 |
| **turbo3_tcq** | 208.1 | 3.25 | **0.025535** |
| V16 | 196.0 | 3.06 | 0.055170 |

## Scored against the prereg

Interpolation, as registered: per chunk, log(KLD) is linear in log(allocation) between the two bracketing VBR arms.
Exact sign-flip permutation over 18 chunks (minimum p = 7.6e-6). A pass needs >= 16/18 chunks lower (Amendment 1).

| # | claim | result | verdict |
|---|---|---|---|
| R1 | VBR before pressure is f16-exact on CUDA/Pascal | VF differs at 99.99 % of positions, max 7.2e-5, p99.9 5.4e-5, mean ~0 | **FALSE** (numerically, not in quality) |
| R2 | VBR < q8_0 at q8_0's allocation (544 MiB) | VBR 0.000505 vs 0.000425 (+19 %), 2/18 chunks lower, p = 0.66 | **FAIL** |
| R3 | VBR < q4_0 at 288 MiB | VBR 0.022845 vs 0.015745 (**+45 %**), 1/18 lower, p = 1.5e-5 | **FALSE, reversed** |
| R4 | VBR < turbo3_tcq at 208 MiB | VBR 0.048206 vs 0.025535 (**+89 %**), 0/18 lower, p = 8e-6 | **FALSE, reversed** |
| R5 | the VBR curve is monotone | 0.0552 > 0.0291 > 0.0149 > 0.0039 > 0.00018 > 0.000008 | **PASS** |

`turbo4` (frontier point, not a test): 0.0163 against VBR's 0.0291 at the same 264 MiB.

**Registered reading:** R2-R4 false -> VBR's allocator advantage does **not** generalize from Qwen3.5-9B on ROCm
(`kv-depth`: -71 % vs q8_0) to Qwen3.8-27B on CUDA/Pascal at this depth. R1 false -> VBR's CUDA path is not
bit-identical to f16 before pressure on Pascal. The deviation is about 1e-5, 1-3 orders of magnitude below every
comparison above.

## Where the loss comes from (descriptive)

1. **Mapping overhead: VBR maps ~40 MiB more than its budget at every size** (+32 to +46 MiB; budget 563 -> 604,
   225 -> 264). That is 6 % of the allocation at V75 and 16-20 % at V22/V16. Scoring on the *budget* axis instead
   removes this, and gives the allocator's own contribution:

   | at the allocation of | VBR (budget axis) vs static | chunks VBR lower | p |
   |---|---:|---:|---:|
   | q8_0 (544) | -44 % | 3/18 | 0.50 (not significant; the mean is carried by a few chunks) |
   | q4_0 (288) | +1 % | 13/18 | 0.86 (a tie) |
   | turbo4 (264) | +20 % | 8/18 | 0.037 |
   | turbo3_tcq (208) | +33 % | 2/18 | 0.003 |

   Without the overhead, VBR ties at ~4.5 bpv and still loses below it.
2. **The allocation is deep and uneven.** The degrade order is `160 baked steps (arch + KV-layout matched; n_layer
   65 vs table 64 -- MTP/nextn-style variant)`: the table measured on **Qwen3.6-27B**, applied to Qwen3.8-27B.
   - It sends some tensors to `turbo2_tcq` / `turbo1_tcq` while most layers are still at turbo4-turbo8.
   - V29 (5.31 bpv on average) logged per-chunk degrades to t1 x1, t2 x2, t3 x11, t4 x32 and t8 x32.
   - A uniform codec at a lower average (q4_0, 4.5 bpv) beats it. On this model, the cheapest-first price order buys
     bits, not fidelity (the same observation as `vbr-fidelity` 08-25, now at matched bytes).

## What this means

- **VBR's value on this fleet is elasticity, not fidelity per byte.** It lets `.73` hold a 262k context on 32 GB at
  whatever depth the prompt reaches, and it is exact-ish before pressure. At a fixed, known budget, a static uniform
  codec is as good or better on this model.
- **`.73`'s operating points, read off the curve:**
  - at 5.83 bpv (observed at 128k), about KLD 0.0095;
  - at the t4 floor (4.125 bpv), about 0.029, roughly 1.8x turbo4's 0.016 at the same bytes.
- **For buun:**
  - the ~40 MiB constant mapping overhead;
  - whether the Qwen3.6-27B table should apply to Qwen3.8-27B;
  - whether early t1/t2 steps belong in the order at all at mid budgets;
  - the f16-tier numerical difference on Pascal (tiny, but not bit-exact, unlike ROCm).

## Not established

- One weights file, and it is a 2-bit body (Q2_K_XL). KV sensitivity could differ at higher weight precision;
  kv-depth used a Q8_0 9B.
- One text (wikitext), 16k depth, frozen VBR (the allocator, not the live controller), Pascal only.
- The price-table question is inferred from the log line, not tested (a Qwen3.8-measured table would be the test).
- Compared with kv-depth, four things change at once (model, precision of weights, backend, depth). This receipt
  cannot say which one flips the result.
