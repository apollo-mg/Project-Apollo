# Tier-4 metric 2 — inter-token latency as a distribution

**2026-08-19.** Closes the one **need** on the tier-4 sheet
(`hle-mini/DESIGN_STACK_VIABILITY.md`, metric 2). Tool: `latency_profile.py`.

Streams the completion and timestamps every token as it arrives. GN translation kept literal:

| GN | here |
|---|---|
| average FPS | mean t/s |
| **1 % low FPS** | **throughput implied by the mean of the slowest 1 % of inter-token gaps** |
| 0.1 % low | same, slowest 0.1 % |
| frame time | inter-token gap, ms, at p50 / p90 / p99 / max |

Depth arms are included because TTFT at ~0 context is the one case nobody actually runs.

## Smoke test — not a result

`Qwen3.5-9B-Q8_0`, `q8_0` KV, RX 9070 XT, ctx 17,792, `n_predict` 384, **one pass per depth**.

| prompt depth | TTFT s | mean t/s | 1 % low | 0.1 % low | p50 ms | p90 ms | p99 ms | max ms |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 0.059 | 56.69 | **20.10** | 19.01 | 17.28 | 17.40 | **40.25** | 52.61 |
| 2,048 | 0.061 | 57.52 | 50.78 | 49.68 | 17.35 | 17.44 | 18.78 | 20.13 |
| 16,384 | 0.080 | 55.70 | 48.96 | 47.60 | 17.93 | 18.02 | 19.32 | 21.01 |

**Zero context has the worst frame-time consistency of the three**, which is the opposite of
what a mean-only benchmark would suggest: 1 % low of 20.10 t/s against a 56.69 mean, and p99
more than double the deeper arms.

**Do not quote this.** `n=1` per depth, and the depth-0 outlier is plausibly warm-up surviving
the 16-token warm pass — a short prompt may not touch the same kernels a long one does. It
needs repeats, and if it survives them it is worth its own panel.

TTFT moving only 0.059 → 0.080 s from 0 to 16k on this model/card is also unrepeated.

## What it does not do yet

- **No power correlation.** Metric 4 (tokens/joule) needs the `S2` sampler running alongside;
  they are separate scripts today.
- **Single stream only.** No concurrency arm, so nothing here describes behaviour under load.
- **No fidelity gate.** Timing only.
