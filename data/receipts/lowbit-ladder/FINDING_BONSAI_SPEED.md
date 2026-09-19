# Finding -- Bonsai ternary costs 2.67x the compute of a stock IQ2_XS on sm_60

**2026-09-19, measured incidentally during the ladder.** Prompted by Mark's recollection that
*"Bonsai pays a steep performance penalty too."* It does, and the panel isolated it for free.

## The measurement

`llama-perplexity` prints `seconds per pass` after the first chunk. Three runs, same corpus, same
reference, same frozen flags, same two P100s:

| run | binary | model | codec | **s/pass** |
|---|---|---|---|---:|
| G-IQ2XS | buun-sm60-qual | GSQ-RCO IQ2_XS | IQ2_XS | 19.01 |
| C-XBIN | **prism** | **GSQ-RCO IQ2_XS** | IQ2_XS | 19.24 |
| B-PTQ1 | **prism** | Bonsai 2 | **PTQ1_0 ternary** | **51.30** |

**The two variables are separated:**

- **Binary overhead: +1.2%.** C-XBIN vs G-IQ2XS is the *same model* on two different llama.cpp
  lineages -- 19.24 vs 19.01 s/pass. Essentially free.
- **Codec cost: 2.67x.** B-PTQ1 vs C-XBIN is the *same binary* with a different codec -- 51.30 vs
  19.24 s/pass.

That C-XBIN exists at all is why this is clean. It was added as Amendment 1's cross-binary
*fidelity* control; it doubles as the speed control, which was not its purpose.

## The caveat that has to travel with the number

**This is the Pascal fallback path, not the codec's designed performance.** The prism fork ships
`ggml/src/ggml-cuda/mmq-config-ampere.cuh` -- the tuned MMQ configuration targets **Ampere**. On
sm_60 the ternary types will not hit that path and almost certainly fall back to dequantise +
BLAS, which is exactly the pattern `exl3-on-pascal` records for other formats on this hardware
("sm_60 never gets MMQ for dense GGUF").

So the honest statement is:

> **On a Tesla P100 with fallback kernels, Bonsai 2 ternary costs 2.67x the compute of a stock
> IQ2_XS.** On hardware the codec was tuned for, the penalty is unmeasured and could be far
> smaller.

Quoting "Bonsai is 2.7x slower" as a general fact would be wrong. Quoting it as "2.7x slower on
Pascal, where it runs the fallback path" is supported.

## Why it matters for the low-bit argument

A codec's value is fidelity per byte **and** throughput per byte. This panel measures the first
rigorously and has now stumbled into a number for the second. If a 1.75 bpw quant is 2.67x slower
to run, then in tokens-per-second-per-gigabyte it can lose to a larger, faster quant that fits
just as well -- and the VRAM saving buys nothing if the card sits idle waiting on dequantisation.

**Unmeasured and worth measuring:** this is batch perplexity throughput at `-b 512 -ub 8`, which
is prefill-shaped. **Interactive decode is latency-bound and a different question entirely.** The
fleet has the harness for it (`server-uptime-is-a-variable` discipline, restart before each leg),
and both Bonsai containers are already staged on `.73`.
