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


---

# CORRECTION -- 2026-09-19 14:05: the 2.67x applies to PTQ1_0 ONLY. PQ2_0 is FASTER than stock.

B-PQ2 completed and reverses the headline above for the other container.

| cell | container | scored bpw | **s/pass** | wall clock |
|---|---|---:|---:|---:|
| B-PTQ1 | dense trits, 5 per byte | 1.748 | **51.30** | 2180s |
| **B-PQ2** | **2-bit slots** | 2.119 | **14.58** | **747s** |
| C-XBIN | stock IQ2_XS, same binary | 2.476 | 19.24 | 1026s |

**PQ2_0 is 2.92x faster than PTQ1_0 and 24% faster than a stock IQ2_XS on the same binary.** It is
the fastest cell in the entire eight-cell panel.

So "Bonsai ternary costs 2.67x the compute of a stock IQ2_XS" -- the title of this receipt -- is
**true only of PTQ1_0**. The mechanism is the packing, not the ternary format: unpacking 5 base-3
trits from a byte requires division and modulo by 3, while 2-bit slots need only shifts and masks.

**Combined with P-L5 (the two containers agree to 3.2e-5), this makes PQ2_0 strictly dominant
over PTQ1_0 except on size**: identical fidelity, 2.92x the speed, 21% more bytes.

It also answers the question that prompted this measurement -- *what does the extra bpw in the
wider container buy?* Earlier reasoning in `ANALYSIS_BONSAI_V1_VS_V2.md` concluded "nothing, it is
container padding". **That was wrong.** The extra 0.371 bpw buys **decode speed**, which is a real
and deliberate engineering trade, not waste.

The Pascal-fallback caveat still stands for both numbers: the prism fork's tuned MMQ config targets
Ampere, so neither container is running its intended kernel on sm_60.
