# Pre-registration — turbo FA at hsk=256, GQA sweep, gfx1201

**Written 2026-09-03, before building or running anything.** Instrument:
`test-backend-ops -o FLASH_ATTN_EXT` in `engines/tq_head` (gfx1201, ROCm), patched to add
FA cases the suite has never carried.

## Why this test exists

`RESULT_TCQ_2BIT_RDNA4.md` measured 8/8 turbo KV configurations collapsing generation on
Qwen3.8-27B (hsk=256, GQA 6:1) on gfx1201, while Qwen3.5-9B (hsk=256, GQA **4:1**) runs the
same codecs clean. That receipt attributed it to "GQA >= 6 / this model class". Two competing
explanations were live as of today:

- **H1 (hybrid):** the discriminator is the SSM/attention hybrid structure.
  **ALREADY FALSIFIED before this run** — Qwen3.5-9B is `full_attention_interval = 4` too
  (verified from its GGUF header today). Both models are hybrids. H1 is dead.
- **H2 (GQA ratio):** the discriminator is `gqa_ratio = n_head / n_head_kv`, threshold at 6.
  Corroborated externally by `turboquant#311` (poshih, RTX 3090, **CUDA not HIP**,
  `qwen35moe`, GQA 8:1, q8_0-K + turbo4-V) — a collapse on completely different hardware.
- **H3 (head size):** the discriminator is hsk=256 with turbo, independent of GQA.

This test separates H2 from H3 with no model, no template, no sampler.

## Coverage gap this closes (source-level, already verified, no build needed)

| tree | commit | turbo types in the FA sweep | head sizes for non-F16 KV | nr2=6 tested? |
|---|---|---|---|---|
| `tq_head` (turboquant HEAD) | `f97400563` | TURBO3_0, TURBO4_0 | `hsk != 64 && 72 && 128` -> skip | **yes, but `hsk != 128` -> skip** |
| `llama_cpp_turboquant` (older) | `c26cbdffc` | TURBO3_0, TURBO4_0 | same | **no — nr2=6 absent entirely** |
| `buun-llama-cpp` | `7a918624b` | **none** | `hsk != 64 && 72` -> skip | no |

Corrected mid-write after reading `tq_head` rather than assuming it matched the older tree:
**GQA 6 with turbo IS covered at hsk=128** (`nr2 == 6 && hsk != 128 -> continue`, added with an
explicit "non-power-of-2 GQA ratio" comment). So the remaining hole is narrower and sharper
than the one I first wrote down:

- **hsk=256 with any quantized or turbo KV is never tested in any of the three forks.**
- buun's fork ships **VBR**, whose degrade ladder puts a turbo tier at **step 1**
  (`llama-vbr-degrade-orders.inc`), and carries **zero** turbo FA coverage at any head size.
- Coverage existing in the suite is not the same as coverage being *run*: Tom's fleet has no
  AMD hardware, so no gfx1201 has ever executed even the hsk=128 nr2=6 turbo cases in CI.

Qwen3.8-27B / Qwen3.6-27B / Qwen3.6-35B-A3B are all hsk=256 — the whole Qwen3.5+ KV shape.

## Predictions (logged before the run)

| # | prediction | confidence |
|---|---|---|
| P1 | F16 K/V at hsk=256 passes at every nr2 including 6 (control) | 0.95 |
| P2 | At least one turbo type FAILS the NMSE gate at hsk=256, nr2=6 | 0.75 |
| P3 | The same turbo type PASSES at hsk=256, nr2=4 (isolating GQA, H2 over H3) | 0.40 |
| P4 | Q8_0 K/V at hsk=256 nr2=6 passes — i.e. the fault is turbo-specific, not quantized-KV-generic | 0.70 |
| P5 | Failures, if any, are NOT confined to one turbo bit depth (turbo8 and turbo2 both affected), matching the receipt's "bit depth is irrelevant" | 0.65 |
| P6 | Some hsk=256 turbo instantiations report **not supported** and silently fall back to CPU rather than failing | 0.35 |

**P3 is the load-bearing one, and I have downgraded it 0.55 -> 0.40 on the coverage finding
above.** GQA 6 + turbo already passes CI at hsk=128, which is evidence against a pure-GQA
fault and shifts weight to H3 (head size 256). If turbo fails at BOTH nr2=4 and nr2=6 at
hsk=256, H2 is wrong, the discriminator is head size, and the receipt's Qwen3.5-9B "clean"
control needs re-examining — that model is hsk=256 too, so under H3 it should have collapsed
and did not.

**Falsification condition for the whole exercise:** if every turbo case passes NMSE at
hsk=256 across all nr2, then the collapse is not visible at the kernel-op level and lives
higher up (cache write/read path, VBR transcode, slot reuse) — which is itself a result and
redirects the search.

## Scoring
Scored in `RESULT_TURBO_FA_GQA_SWEEP.md`. Every case's NMSE recorded, pass or fail.
