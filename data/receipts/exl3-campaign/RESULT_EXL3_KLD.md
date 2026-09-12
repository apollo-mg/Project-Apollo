# Result — at matched VRAM, EXL3 is 24% closer to the reference than the GGUF of the same size; perplexity ranks them the other way

**Run 2026-09-12, 16:21–18:08, on `.73`'s two P100s.** Pre-registered in `PREREG_EXL3_KLD.md`
(`8b9cd65`) with Amendment 1 (`f68b43e`), and scored by `tools/score_exl3_kld.py`, committed with the
prereg. Raw data in `kld/`. EXL3 campaign test 3, ledger entry O6 (the distributional half).

**Reference:** the Q8_0 from `unsloth/Qwen3.8-27B-GGUF` @ `4ca72078`, sha256 `a680f44a…b67e348`, run
with `--kl-divergence-base`. Every arm ran the same binary (buun `9ae8f0f40` + e8m0 guard), the same
40 chunks of wikitext-2 at `-c 512`, and `-ub 8` so that every matmul stayed on the small-batch decode
kernels.

## Results

| arm | disk GB | peak VRAM MiB | mean KLD ± | median KLD | 99% KLD | same top-1 ± | PPL(Q) |
|---|---|---|---|---|---|---|---|
| **R2** Q8_0, the gate | 29.05 | 26,746 | **0.000000 ± 0.000000** | -0.000000 | 0.000038 | **100.000 ± 0.000** | 5.9325 |
| **E** EXL3 4.00bpw | 16.88 | **13,468** | **0.012002 ± 0.000379** | 0.004101 | 0.148772 | 95.431 ± 0.207 | 5.9535 |
| **G4** UD-IQ4_XS | 14.25 | 13,500 | 0.015727 ± 0.000383 | 0.006376 | 0.166563 | 94.245 ± 0.231 | 5.9490 |
| **G5** UD-Q4_K_M | 16.46 | 15,448 | 0.007840 ± 0.000232 | 0.002917 | 0.078477 | 96.225 ± 0.189 | 5.9311 |
| **G6** Q6_K, the daily driver | 22.88 | 21,276 | 0.002770 ± 0.000240 | 0.000986 | 0.023571 | 97.657 ± 0.150 | 5.9186 |

**EXL3 strictly dominates the GGUF at its own size.** Against UD-IQ4_XS it has **24% lower mean KLD at
32 MiB less VRAM**, and holds top-1 agreement 1.2 points higher. Mean, median and same-top all agree on
that ordering.

## Predictions

| id | prediction | result |
|---|---|---|
| P-K0 | **Gate:** R2's KLD < 1e-4 and same-top ≥ 99.9% | **CONFIRMED.** KLD 0.000000, same-top 100.000% — the reference reproduces bit-for-bit across processes |
| P-K1 | E's mean KLD below G5's | **FALSIFIED.** 0.012002 vs 0.007840. Q4_K_M, 2 GB larger, is closer |
| P-K2 | E's mean KLD below G4's | **CONFIRMED.** 0.012002 vs 0.015727, a gap ~5× the summed uncertainties |
| P-K3 | G6's mean KLD below E's | **CONFIRMED.** 0.002770 vs 0.012002 |
| P-K4 | E's same-top ≥ 95.0% | **CONFIRMED.** 95.431 ± 0.207% |

**The headline rule did not apply, and the receipt says so rather than bending it.** The prereg placed
EXL3 on the GGUF curve only if two GGUF arms bracketed its VRAM. EXL3 landed **32 MiB below** the
smallest GGUF arm, so nothing brackets it from beneath and the scorer reported dominance instead. Had
EXL3 been 33 MiB larger, the interpolation would have applied and put it ~25% below the curve. The
dominance statement is the stronger claim anyway.

## Two things worth more than the verdicts

**1. Perplexity fails demonstrably on this run.** Ranked by PPL: G6 5.9186, G5 5.9311, **the reference
itself 5.9325**, G4 5.9490, E 5.9535.

- **Two quantized models score better perplexity than the Q8_0 they are approximating.** As a fidelity
  claim that is incoherent: the reference cannot be worse at being itself.
- **KLD orders all four correctly** by distance from the reference, and its ordering matches same-top.
- **The two metrics disagree about EXL3 specifically:** perplexity puts it last of four, KLD puts it
  second. Any comparison of these files that quotes only perplexity — including our own earlier
  "+0.55%" — is quoting the metric that gets the reference wrong.

**2. What the advantage is worth, in VRAM.** Interpolating the GGUF curve log-linearly between G4 and
G5, a GGUF needs about **790 MiB more VRAM (+5.9%)** to reach EXL3's mean KLD. That is the honest
exchange rate for the format, and it should be read next to the **~35% decode cost** measured in test 1.
*(Descriptive: an interpolation on three GGUF points, not a preregistered claim.)*

## What this does not settle

- **This is one corpus and one context length.** Wikitext is not the daily driver's workload, and no
  claim here is about task accuracy. That is the other half of O6 and is unrun.
- **The distribution is long-tailed.** EXL3's 99th percentile (0.1488) is 12× its mean, and its median
  is a third of its mean. The mean is moved by a small number of tokens, which is why the prereg scored
  differences against summed uncertainties and reported medians alongside.
- **KLD measures distance from a reference, not quality.** A model can move its distribution and still
  write working code, or hold it and still break a tool call. Even buun uses KLD panels ordinally —
  to choose which VBR tier to degrade next (`docs/vbr.md:28,140`), not as a verdict.
- **`-ub 8` measures the decode kernels.** A prefill-kernel KLD could differ.
- **The comparison against larger GGUFs is not yet like-for-like.** EXL3 ships a bitrate ladder
  (2.00 … 6.00bpw), so the fair opponent for Q4_K_M at 15.4 GB is an EXL3 near that size, not EXL3
  4.00bpw. Mark caught this framing error; Amendment 2 adds the 5.00bpw arm against the same reference.
- **Cross-run perplexity needs matching `-ub`.** This run's numbers are not comparable to the inference
  receipt's, which used the default `-ub 512` with `-ts 3,2`.

## Deviations

- **The Q6_K arm is a different upload revision** (`db81afd1e1`) from the three arms at `4ca72078`. It is
  the daily driver's actual file, which is the point of including it.
- **A proxy restart collided with the last arm.** At 17:56 the next test's orchestrator misread an
  aborted predecessor as a finished one, stopped and restarted the wake proxy, and its GPU check then
  refused to run. The 18:05 ledger request consequently reached a live proxy, which tried to launch the
  daily driver onto GPUs holding this test's Q6_K arm and died with `cudaMalloc failed: out of memory`
  after 9 s. **The arm itself completed rc=0 with no failed decode**, and KLD arithmetic does not depend
  on another process's failed allocation — but the wall time for G6 spans that event. Fixed in `6300b36`:
  orchestrators now wait for `.73` to be genuinely free and check it before touching the proxy.
- **The driver's `pgrep -x llama-perplexity` guard is inert** (Amendment 1): `pgrep -x` matches a
  15-character process name and that string is 16. The GPU-memory check is what enforced exclusivity.
- **The dev-diary ledger lost its 16:05, 17:05 and 18:05 runs** while the proxy was paused.
