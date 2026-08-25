# VBR at 3.25 bpv is indistinguishable from f16 — and the price table buys bits, not quality

**2026-08-25**, `.194` GPUs 0,1, 2× Tesla P100 (sm_60), 1063 MHz / 150 W.
buun `7d30a7244` (`build_sm60_new`, sm_60 routing fix present). `Qwen3.8-27B-UD-IQ4_XS`,
`-sm tensor -fit off -c 32768 -np 1`, card sampling (temp 1.0 / top_p 0.95 / top_k 20),
**`reasoning_effort` pinned to `medium`**, 3 seeds × 16 items = 48 cells per arm.
Pre-registration: `PREREG_VBR_FIDELITY.md`. Raw `fid_*.jsonl`.

**Conflict of interest:** Mark collaborates with the codec's author. Method was fixed in advance
and the unfavourable outcomes were named before the data existed. `G2` — the headline
prediction — **failed**, and is reported as such below.

## Result — all arms at matched context depth (~29k tokens)

| arm | KV bytes | achieved bpv | confab | abstain | acc | NO-STOP | t/s |
|---|---:|---:|---:|---:|---:|---:|---:|
| `F16` | 1,824 MiB | 16.0 | 1/24 | 23/24 | 24/24 | 0 | 13.83 |
| `CBR325` static `turbo3_tcq` | **370 MiB** | 3.25 | 1/24 | 23/24 | 24/24 | 0 | 8.61 |
| **`VBR416`** `--vbr-vram 416M --vbr-floor t1` | **371 MiB** | **3.254** | 0/24 | 24/24 | 24/24 | 0 | 9.07 |
| **`VBR416R`** same budget, **reversed** order | **371 MiB** | **2.172** | 1/24 | 23/24 | 24/24 | 0 | 9.74 |

## What holds

**1. A 4.9× KV compression costs nothing measurable.** `CBR325` and `VBR416` both match `F16` on
calibration within one item at n=24 — while using **370 MiB against 1,824 MiB**. No `!`-collapse,
no non-termination, answerable accuracy 24/24 everywhere.

**2. `G2` FAILED — VBR does not beat CBR at matched bytes.** Registered at 0.50. VBR is one item
better on confabulation, which is noise at this sample size. **At the same byte budget, the
price-ordered allocation and the flat allocation produce indistinguishable calibration.**

**3. But the price table does measurable work — on a different axis.** Same 416 MiB budget:

| order | achieved aggregate |
|---|---:|
| correct (`q27`) | **3.254 bpv** |
| reversed | **2.172 bpv** |

**A 33 % worse aggregate from identical bytes.** The table is not buying quality-per-bit; it is
buying **bits-per-byte**, which is what a price-ordered water-fill allocator is supposed to do.
A bad order wastes the budget by demoting cheap-to-keep units too far.

## What this does NOT establish

- **16 items is a gate, not a measurement.** Every arm landed within one item of every other.
  This instrument has a **sensitivity floor**: it can detect codec differences large enough to
  move 24-sample calibration and nothing smaller. A tie here is *not* evidence of no difference.
  `BACKLOG A1` (the ~240-pair corpus) is what would resolve it.
- One model, one quant, one architecture, one context depth.
- The reversed-order control is imperfect: the source states a custom `VBR_DEGRADE_ORDER`
  "carries no band guarantee, so it disables demand shedding", so `VBR416R` differs from
  `VBR416` in more than ordering alone.

## An unregistered finding: context depth moves calibration

The same `F16` arm, same items, same seeds, differing only in prefix length:

| ctx | confab | abstain |
|---|---:|---:|
| ~0 | 3/24 | 21/24 |
| ~29k | **1/24** | **23/24** |

**Deeper context made the model more cautious.** This was discovered as a confound — the first
`VBR416` run measured at 29k against static arms measured at 0, and scored a suspiciously
perfect 0/24. Matching depth was necessary for the comparison and surfaced this on the way.
n=1 pair, unregistered, and worth a proper arm.

## Operational gotchas found while measuring

| gotcha | consequence |
|---|---|
| `realized_bpv` is **null in dynamic mode by design** (`server-context.cpp:15205`) | reads as "controller not engaging"; cost a day |
| **`/props` misreports `floor_bpv`** — passed `t2`, reported `4.125`, log said `2.25` | **the server log is authoritative, `/props` is not** |
| **entry tier is f16** | short conversations are f16 in disguise; benchmarking VBR at low fill measures f16 |
| advertised `n_ctx` ignores the budget | 262,144 advertised on a 384 MiB budget holding ~12k at f16 |
| explicit `-ct vbr` defaults to a **t1 (1.25 bpv) floor**, not the implicit t4 | easy to land in the worst tier by accident |
| custom `VBR_DEGRADE_ORDER` disables demand shedding | the override is not a drop-in equivalent |
| **Qwen3.8 runs the `q27` table generated for Qwen3.6** | never scanned (confirmed by the author). Given the reversed-order result shows the table matters, this is worth closing |
