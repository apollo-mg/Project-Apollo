# turbo4 stability repro bundle — for buun's RDNA4 card

One script. Run it when the 9070 is up; it answers "does the turbo4 nondeterminism reproduce on
my own hardware" in about 25 minutes, and it validates itself while doing so.

## Run it

```bash
BIN=/path/to/buun-llama-cpp/build/bin \
MODEL=/path/to/Qwopus3.5-27B-v3-Q2_K.gguf \
DATASET=/path/to/wikitext-2-raw/wiki.test.raw \
./turbo4_stability.sh
```

Optional: `N=12` reps per arm (default 12), `REF_BIN=/path/to/another/fork/build/bin` to add a
cross-fork control, `OUT=/somewhere`.

Any GGUF and any real wikitext-2 will do — the finding is about run-to-run *variance*, not the
absolute PPL. Using the same model as us just makes the numbers directly comparable.

## What we measured (RX 9070 XT / gfx1201, buun-llama-cpp @ `7939b6c47`, Qwopus3.5-27B-v3-Q2_K)

| arm | result |
|---|---|
| **f16 KV** | **bit-stable — 7.4948 on every single run** |
| **turbo4 KV** | **2/22 runs hard NaN (~9 %)**; 11 finite runs spanned **8.0984–8.1825**, every one different |
| TheTom's fork, turbo4 | bit-stable, 7.4880 every run |

Re-confirmed 2026-07-30 with this exact script, `N=3`: f16 `7.4948 / 7.4948 / 7.4948`
(spread 0.0000); turbo4 `8.1465 / 8.1585 / 8.1950` (spread 0.0485). The turbo4 max extended
slightly past the earlier range, which is what you'd expect from real nondeterminism as samples
accumulate.

## How to read the output

The script prints this, but it's the whole point so it's here too:

| outcome | meaning |
|---|---|
| **f16 BIT-STABLE + turbo4 UNSTABLE** | reproduces — it's the turbo decode path |
| **f16 UNSTABLE** | **stop.** Your box or build is the variable; any turbo4 number is void |
| **both BIT-STABLE** | does not reproduce on your setup — worth reporting build + card |

**The f16 arm is not padding, it's the validity gate**, and it runs first for that reason.
`llama-perplexity` is a deterministic harness, so f16 coming back bit-identical proves determinism
*on your machine, in that session*, before turbo4 is interpreted at all. Neither arm means
anything alone; the contrast is the evidence.

## Three gotchas that cost us time

**1. The NaN run exits 0.** It prints `Unexpected negative standard deviation of log(prob)` to
stderr and returns success. Anything checking `$?` misses it completely — that's why it went
unnoticed initially. This script detects on the *output* (missing `Final estimate`, or a literal
`nan` in the log), never on the exit code.

**2. A truncated corpus silently voids the whole run.** A placeholder `wiki.test.raw` once
invalidated an entire PPL leg here. The script aborts if the dataset is under 100 KB; real
wikitext-2 test is ~1.3 MB.

**3. Run every cell more than once.** The NaN and the drift were both found only because cells
were run twice as a habit. A single PPL number from a nondeterministic path is not a measurement.

## Not applicable here: the llama-server determinism gotcha

Separately we found that on this stack `llama-server` needs **`-cb` off** *or*
`cache_prompt:false` to produce reproducible temp-0 output — with both continuous batching and
prompt caching enabled, output varies run to run (upstream: *"we use different kernels for
different batch sizes"*, ggml-org/llama.cpp#23335).

**That does not affect this repro.** `llama-perplexity` has no prompt cache and no continuous
batching, and the bit-stable f16 arm demonstrates it empirically. Flagging it only because it
*will* matter the moment you benchmark through the server instead — it's an easy way to spend
days chasing phantom variance.

## Interpretation

f16 stable and turbo4 unstable on the same fork, same card, same session isolates this to the
turbo decode path rather than the hardware or the build. The NaN and the drift look like one
underlying thing: usually it perturbs the result slightly, occasionally it lands somewhere that
produces NaN.

For contrast, on this same RDNA4 card **turbo3 is completely clean** (12/12 healthy across HIP and
Vulkan) — the turbo3 corruption in turboquant#241 is Polaris/GCN4-specific and won't appear on a
9070.
