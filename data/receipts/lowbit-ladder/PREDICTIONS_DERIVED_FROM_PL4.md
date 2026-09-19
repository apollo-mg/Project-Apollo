# Derived predictions from P-L4, recorded before anyone tests them

**2026-09-19 13:54, B-PQ2 still loading.** P-L4 measured on B-PTQ1: at equal KLD, the ternary cell
sits **0.764 pp below** a scalar cell on same-top (77.284% expected vs 76.520% measured). The
rotated ternary basis damages the **argmax** more than it damages the **distribution**.

Three consequences follow. They are preregistered here so they are scored honestly if anyone runs
them, and so the reasoning is on record before the outcome is known.

## P-D1 -- ternary should do relatively BETTER on distribution-consuming tasks than on generation

Prompted by mmastrac asking whether Bonsai is worth trying for summarisation or embeddings.

If top-1 is damaged disproportionately while the distribution stays comparatively close, then:

| task type | consumes | expected ternary penalty |
|---|---|---|
| generation / agentic | the **argmax** (sampled from the top) | **larger** |
| embeddings, scoring, reranking, classification | the **distribution** or hidden states | **smaller** |

**Prediction:** measured against its own full-precision reference, Bonsai 2's relative degradation
on an embedding/reranking task is **smaller** than its relative degradation on a generation task.
**Falsified if** the two penalties are equal, or generation is the better-preserved one.

**Why this matters practically:** it would mean the codec's worst-reported use (agentic
generation, per the public reports) is the one that exposes its specific weakness, and that a user
doing retrieval or classification is operating in the regime where it costs least. The advice
"Bonsai is bad" may be task-conditional rather than general.

## P-D2 -- the 2.67x GPU penalty should not transfer to multiplier-free hardware

Prompted by h4rm0n1c noting that squeezed formats make a cheap FPGA more interesting.

Ternary weights are {-1, 0, +1}: a matmul against them needs **no multipliers**, only adds,
subtracts and skips. The 2.67x compute penalty measured in `FINDING_BONSAI_SPEED.md` is what
happens when a multiplier-free format runs on silicon that is entirely multipliers, through a
dequantise-to-BLAS fallback path (the prism fork's tuned MMQ config targets Ampere; sm_60 does not
reach it).

**Prediction:** on hardware with native ternary or multiplier-free datapaths (FPGA, or an ASIC
designed for it), ternary's throughput-per-watt advantage over an equivalent-fidelity scalar quant
is **positive**, reversing the sign of the GPU result. **Falsified if** ternary remains slower
per unit of fidelity even on hardware built for it.

**Not measured here and not claimed as measured.** The GPU number is real and the caveat travels
with it: *2.67x slower on Pascal running the fallback path*, never *"ternary is slow"*.

## P-D3 -- EXL3 at TP=4 differs measurably from TP=1

Prompted by mmastrac reporting EXL3 felt "slightly dumber" at tensor-parallel 4.

Tensor parallelism changes the **reduction order** across devices, which changes floating-point
results. On sm_60 the internal AllReduce path fails the cc>=700 check and falls back to NCCL
([[allreduce-internal-inert-on-pascal]]), so the numerics are not merely reordered, they go
through a different implementation.

**Prediction:** a KLD run of the same EXL3 model against the same reference at **TP=1 vs TP=4**
differs by **more than the P-L0 reproducibility floor** (which today measured below 5e-7 within a
binary and 3.1e-5 across binaries). **Falsified if** the two agree to within that floor, which
would make "dumber at TP=4" perception rather than numerics.

`.194` has four P100s and the whole harness already exists. One variable, one reference, no new
code. Nobody has run it, and a subjective report of a model feeling worse is exactly the kind of
claim this fleet exists to put a number next to.
