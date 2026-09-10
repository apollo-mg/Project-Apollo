# Pre-registration — DFlash-2 vs MTP on Qwen3.8-27B, RX 9070 XT 16 GiB

**2026-09-03, before the run.** buun-llama-cpp `3823c9eb6`, gfx1201.
Target `Qwen3.8-27B-GSQ-RCO-IQ3_XXS-mtp` (3.05 bpw, 9.69 GiB, MTP head inline at blk.64 Q6_K).
DFlash-2 drafter `Qwen3.8-27B-DFlash2-BF16.gguf` (**3.43 GiB**).

## The trade, stated before measuring

MTP is **free in VRAM** — the head ships inside the target file (blk.64, 424.7M params at
Q6_K, already counted in the 9.69 GiB). DFlash-2 is a **separate 3.43 GiB model**.

The model is a hybrid: 16 of 65 layers carry KV, **64 KiB/token at f16**. So on a 16 GiB card:

| config | weights | KV headroom* | context at f16 |
|---|---|---|---|
| target + MTP | 9.69 GiB | ~4.3 GiB | **~68k tokens** |
| target + DFlash-2 BF16 | 13.12 GiB | ~0.9 GiB | **~14k tokens** |

*after ~2.0 GiB measured overhead (desktop + compute + SSM state).

**DFlash-2 costs roughly 54,000 tokens of context.** The question is not "which is faster" —
it is whether the speedup is worth that, and the honest answer depends entirely on the
workload's context length.

## Prior art

`RESULT_S2_DFLASH_PASCAL.md` (2026-08-18) measured this pair on **Qwen3.5-9B**:
RX 9070 XT, MTP 107.95 t/s vs DFlash 116.68 t/s at n=3 (**+8%**); at n=7,
104.53 vs 140.03 (**+34%**). On Pascal the curve inverted. That was a 9B target with a
1.3 GB drafter — a far cheaper ratio than 3.43 GiB against a 27B.

## Predictions

| # | prediction | conf |
|---|---|---|
| P1 | Both spec modes beat no-spec on decode t/s at temp 0 | 0.90 |
| P2 | DFlash-2 beats MTP on raw decode t/s, as it did on the 9B at n>=3 | 0.60 |
| P3 | The margin is **smaller** than the 9B's +34% at n=7, because the 27B target is slower per step so drafter overhead amortises differently | 0.55 |
| P4 | DFlash-2 + target does NOT fit at `-c 32768` (needs ~2.0 GiB KV on top of 13.12 GiB) | 0.85 |
| P5 | At matched `-c 8192` both fit, and the comparison is clean | 0.75 |
| P6 | MTP wins on tokens/s **per GiB of VRAM spent**, by a wide margin, regardless of who wins raw t/s | 0.80 |

**The decision-relevant one is P6.** Raw t/s is the wrong axis on a 16 GiB card; the receipt
must report throughput against context sacrificed, not throughput alone.

## Method

`-c 8192` on every arm so the comparison is matched and everything fits. `-fa on --jinja
--kv-unified -np 1`, f16 KV, temp 0, seed 42, K=3, identical prompts.
Arms: (a) `--spec-type none`; (b) `--spec-type draft-mtp`; (c) `--spec-type draft-dflash
-md <drafter>`. Record decode t/s from server timings, acceptance rate where reported, and
peak VRAM. Readiness gated on `/props` model identity (a `/health` 200 proved nothing
earlier today — port 8099 is `apollo-wake-proxy`).

**Falsification that would matter:** if DFlash-2 wins raw t/s by enough that it still wins
per-GiB, P6 is wrong and the drafter is worth its footprint even on a 16 GiB card.
