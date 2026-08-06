# Prefix cache reuse changes temperature-0 output — upstream llama.cpp, default-on

**2026-07-27.** Node `.73`, dual Tesla P100 (sm_60), 1063 MHz / 150 W.
Model `Hermes3.6-35B-A3B-Uncensored-Genesis-V5-APEX`. `/completion` with a raw prompt (no
chat template), `temperature 0`, `top_k 1`, `top_p 1.0`, `seed 1234`, `n_predict 400`.

## Result

Same request, served two ways:

| build | path | tokens prefilled | sha |
|---|---|---|---|
| `buun_vbr` (vbr KV, `-np 1`) | fresh (`cache_prompt=false`) | 4704 | `0b5c2488a628` |
| `buun_vbr` | fresh again | 4704 | **`0b5c2488a628`** (stable) |
| `buun_vbr` | **cached** (`cache_prompt=true`) | **30** | **`f72bcff327f1`** ← diverges @ char 343 |
| **upstream `0e4a03622`** (f16 KV) | fresh | 4704 | `9d2f00063530` |
| **upstream** | fresh again | 4704 | **`9d2f00063530`** (stable) |
| **upstream** | **cached** | **30** | **`72c3f83e10b1`** ← diverges @ char 641 |

The fresh path reproduces itself byte-for-byte on both builds, so the divergence is not
noise. **Serving a request from a reused prefix produces different output than prefilling it
from scratch**, on genuine `ggml-org/llama.cpp`.

**This is the default.** `common/common.h:622` — `bool cache_prompt = true;`. No flag needed
to hit it; `--no-cache-prompt` is required to avoid it.

## Mechanism (pre-registered before the run, consistent with the result)

Fresh: `C+Q` prefilled together in `-b 1024 / -ub 512` batches.
Cached: `C` already resident, only the ~30 tokens of `Q` prefilled.

Different batch shapes → different GEMM tiling / reduction order → different FP rounding →
perturbed logits → `argmax` flips on a near-tie → divergence compounds. Same mechanism class
as the concurrency finding, reached by a different route.

**Not isolated to a specific batch boundary.** The test shows partial vs full prefill differ;
it does not identify which boundary, and `/slots ... action=erase` returned HTTP 501 on this
build so slots were not cleared between paths. The `cache_prompt=false` arms still performed
full 4704-token prefills and matched each other, so the comparison holds.

## Consequences

- **Multi-turn conversations do not reproduce single-shot ones.** Turn N's output depends on
  whether turns 1…N−1 are cached — which is the normal serving path.
- **Benchmark scenario order is an uncontrolled variable.** Any suite that runs scenarios
  sequentially against one server leaves each scenario's starting cache state dependent on
  what ran before it. HermesAgent-20 does exactly this. **Hypothesis, not yet tested**, but it
  is a plausible additional contributor to the original score variance.
- **`-np 1` alone is not sufficient for reproducibility.** It removes the concurrency channel;
  it does not remove the cache-state channel. Repeated *identical* requests are stable (the
  cache is warm and identical each time — verified 3/3), but interleaved different requests
  are not guaranteed to be.

## Settings consequence

For measurement runs, `-np 1` should be paired with **`--no-cache-prompt`**. Cost: every
request re-prefills. For interactive serving, keep caching — the speedup is the entire point,
and the output is still valid, just not reproducible.

## Relation to the KV-checkpoint article (2026-07-05)

The article ("Llama-Server is Throwing Away Your Perfectly Good KV Caches") shows that slot
save/restore drops checkpoint metadata across a process restart, forcing a full re-prefill,
and fixes it with a sidecar — ~720× delta prefill.

**This result does not invalidate it, and arguably defends it.** The article's ~720× is a
wall-clock claim on an orthogonal axis; nothing here touches save/restore. And the property
one might have held against it — "restored cache changes the output" — is now shown to be a
**universal property of ordinary prefix caching, on by default, upstream.** Restoring a cache
across a restart introduces nothing that serving a second turn in a conversation does not
already do.

Independently: prior evidence says checkpoints are not the driver of the temp-0 variance.
Arm 5 of the six-arm sweep ran `--ctx-checkpoints 0 --slot-prompt-similarity 0` and variance
persisted; today's slot probe ran `cache_prompt=false` and the VBR slot asymmetry appeared
anyway.

**Still untested:** whether save/restore-across-restart specifically diverges *more* than
ordinary cache reuse. Predictable from this result, but not measured. Would need
`--slot-save-path` and a restart cycle.

## The composite picture from 2026-07-27

Three independent channels by which llama-server's temp-0 output depends on **server state**
rather than only on the request:

| # | channel | scope | fixable |
|---|---|---|---|
| 1 | concurrent batched decoding | **upstream** | avoided with `-np 1`; buun says fixable in his tree |
| 2 | **prefix cache reuse** | **upstream, default-on** | avoided with `--no-cache-prompt` |
| 3 | VBR first-use slot asymmetry | fork-specific | buun fixing |

Apparatus: `HermesAgent-20/cache_reuse_probe.py` (fresh vs cached, byte-diff, with a
fresh-path self-consistency control and a cache-actually-engaged check).
