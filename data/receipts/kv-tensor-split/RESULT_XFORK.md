# Cross-fork KV ladder — both bugs are shared, and the collapse needs K *and* V quantized

**2026-08-17.** `.73`, dual Tesla P100 (sm_60), 150 W / 1063 MHz under load.
Binary **TheTom/llama-cpp-turboquant `f6124e9`** (`version: 205`, the #295 merge commit),
built for sm_60 this morning. Same node, same model
(`unsloth-Qwen3.8-27B-Q6_K.gguf`, D=256, GQA 6:1), same flags, same detector and same probe
prompts as `~/kv_pin2.sh`, so this is directly comparable to
`RESULT_TWO_KV_BUGS.md` (buun_vbr `a8e5b5a38`). Raw: `~/xfork/` on `.73`, log `~/kv_xfork.log`.

Predictions were pre-registered in `PREDICTION_XFORK.md` (commit `5d64569`) before launch.

## The matrix

| arm | K | V | split | guard | buun_vbr | **Tom f6124e9** |
|---|---|---|---|---|---|---|
| T1 | f16 | f16 | tensor | 0 | clean | **clean 3/3** |
| T2 | `q8_0` | `q8_0` | tensor | 0 | collapse | **collapse 3/3** |
| T3 | `q4_0` | `q4_0` | tensor | 0 | collapse | **collapse 3/3** |
| T4 | `q8_0` | f16 | tensor | 0 | **HARD ABORT** | **clean 3/3** |
| T5 | f16 | `q8_0` | tensor | 0 | **HARD ABORT** | **clean 3/3** |
| T6 | `q8_0` | turbo4 | tensor | 0 | clean | **clean 3/3** |
| T7 | turbo3 | turbo3 | tensor | **0** | not tested | **HARD ABORT** |
| T8 | turbo3 | turbo3 | tensor | **1** | not tested | **clean 3/3**, K rewritten to `q8_0` |
| T9 | `q8_0` | `q8_0` | **layer** | 0 | collapse | **collapse 3/3** |

## 1. Bug A is not buun-specific — it reproduces exactly

Every collapsed response on Tom's fork is **512 consecutive `/` characters**,
`finish_reason=length`, on the first request, deterministically, for **both** stock codecs,
under **both** split modes. 12 degenerate responses, zero exceptions.

The summary triple is byte-identical to buun's recorded `len=512 maxrun=512 uniq=1`. The
buun run did not save response bodies, so **the `/` is confirmed on Tom's fork only** — the
statistics match, the character is verified on one side. `kv_xfork2.sh` U8 closes that gap.

This kills the mechanism hypothesis this ladder was built on. buun's D=256 dispatch table
(`fattn.cu:2268-2284`) lists only turbo types, and `q8_0` is absent — that looked like the
cause. Tom's `fattn.cu:406` **has** `FATTN_VEC_CASES_ALL_D(GGML_TYPE_Q8_0, GGML_TYPE_Q8_0)`,
instantiated for every head dim, and collapses anyway. Dispatch-table presence does not
predict the outcome.

**Two independently-maintained forks failing identically points at inherited code.** That
makes `BACKLOG C3` — build a genuine upstream reference — the critical path rather than a
nice-to-have. `llama_stock_ref` on `.73` is at `adeff9b82`, a *laguna* commit despite its
`ggml-org/llama.cpp` remote, so **there is still no true upstream binary on this node**.

## 2. The new finding: the collapse requires K **and** V quantized

`RESULT_TWO_KV_BUGS.md` recorded this as an explicit limitation — *"Bug B blocks the clean
isolation of Bug A. The natural control is to hold one side at f16 and quantize the other.
Both of those configurations abort, so that experiment cannot be run on this build."*

**Tom's fork runs it**, because its abort trigger is different:

| K | V | result |
|---|---|---|
| `q8_0` | `q8_0` | **collapse 3/3** |
| `q8_0` | f16 | clean 3/3 |
| f16 | `q8_0` | clean 3/3 |
| f16 | f16 | clean 3/3 |

**Neither side alone is sufficient.** Quantized K is harmless. Quantized V is harmless.
Both together collapse totally. This supersedes the earlier single-variable inference from
buun's arms ("with K held at `q8_0`, swapping V from `q8_0` to turbo4 flips collapse to
clean, therefore **V is implicated**"). That inference was sound given the arms available
there, but it is now known to be the wrong reading: it is not V, it is the pair.

It also re-explains T6. `q8_0` K + turbo4 V is clean not because turbo4 is a better codec
but because turbo4 is not a stock type, so the both-stock condition is never met.

**Still open:** whether the condition is "both stock quantized" or "both the *same* stock
type" — `q8_0` K + `q4_0` V is untested and is `kv_xfork2.sh` U4/U5.

## 3. Bug B is also shared — same assert, different trigger

T7 aborts with the same assert in the same shared file:

```
/home/mark/llama-cpp-turboquant/ggml/src/ggml-backend-meta.cpp:535:
GGML_ASSERT(ret.axis != GGML_BACKEND_SPLIT_AXIS_UNKNOWN) failed
```

Tom line **535**, buun line **533** — a two-line offset in near-identical code. What differs
is *which* KV type combination the split-axis logic cannot resolve:

| fork | aborts on | runs fine on |
|---|---|---|
| buun `a8e5b5a38` | mixed f16 / quantized | turbo symmetric |
| Tom `f6124e9` | turbo3 symmetric | mixed f16 / quantized |

So the defect is shared infrastructure and the trigger set is fork-dependent. **The report
goes to both maintainers**, which is the opposite of what the halfway point of this ladder
suggested.

**The AllReduce warning remains a red herring**, confirmed again: T7 logged it and aborted,
but T1/T4/T5/T6/T8 logged the same warning and ran clean.

## 4. Tom's auto-asymmetric guard prevents a crash, not a quality loss

T7 and T8 are byte-identical command lines differing only in `TURBO_AUTO_ASYMMETRIC`:

| | guard | outcome |
|---|---|---|
| T7 | `0` | **hard abort** at `ggml-backend-meta.cpp:535` |
| T8 | `1` | clean 3/3, log: `upgrading K from turbo3 to q8_0` |

The code comment justifies the guard on fidelity grounds — *"Qwen2.5: 4 KV heads / 28 Q
heads = 7:1 → turbo3 K PPL catastrophic (2887 vs 7.4 baseline)"*. On sm_60 under tensor
split the guard is doing something stronger: without it the server **does not start**.

Two practical consequences:

- **`TURBO_AUTO_ASYMMETRIC=0` is not a usable way to measure honest turbo3 on Pascal.** It
  aborts. Any such measurement needs a different route.
- **With the guard at its default, `-ctk turbo3 -ctv turbo3` on a GQA≥6 model does not
  measure turbo3 symmetric** — it measures `q8_0` K + turbo3 V. Published turbo3 numbers on
  such models describe a different configuration than their label. This model is exactly the
  6:1 threshold.

## Predictions, scored honestly

| # | prediction | conf | outcome |
|---|---|---|---|
| X1 | T2 `q8_0`+`q8_0` **clean** | 0.80 | **FALSIFIED** — collapse 3/3 |
| X2 | T3 `q4_0`+`q4_0` **clean** | 0.75 | **FALSIFIED** — collapse 3/3 |
| X3 | T4/T5 mixed **abort** | 0.70 | **FALSIFIED** — both clean 3/3 |
| X4 | T6 `q8_0`+turbo4 clean | 0.90 | **CORRECT** |
| X5 | T7 turbo3 sym guard-off shows **visible damage** | 0.60 | **WRONG** — it aborted |
| X6 | T8 guard-on clean + upgrade logged | 0.85 | **CORRECT** |
| X7 | T1 f16 clean | 0.97 | **CORRECT** |

**3 right, 4 wrong — and the split is not random.** The three correct calls are the three
highest-confidence ones (0.97, 0.90, 0.85), all of which predicted "nothing interesting
happens." **Every genuine mechanism call was wrong**: X1, X2, X3, X5, plus the composite
("the two bugs separate; Bug A is buun's, Bug B is shared") — in fact **both** bugs are
shared.

The common error in X1/X2/X3 was treating **source presence as behavioural prediction**.
Tom's tree has the `q8_0` dispatch entry and collapses; it has the assert and doesn't fire it
on the pair buun fires on. Reading the code told me where the code was, not what it did.

X5 is the third occurrence of a specific bias — **predicting degradation and getting an
abort** (V1 and V2 in `RESULT_TWO_KV_BUGS.md` were the first two). Logged as **AFM-16**.

The design held even though the calls did not: the matrix carried its own controls, so it
produced the K-and-V isolation regardless of my being wrong about the mechanism.

## What this does NOT establish

- **One head dim.** D=256 throughout, so **N1** stays open. `.73` holds only D=256 models; a
  D=128 model must be copied over.
- **Not localised to flash attention yet.** The `-fa off` control is the single most
  decisive missing arm and is `kv_xfork2.sh` U1/U2. If `-fa off` is clean, this stops being
  "stock quantized KV is broken on Pascal" and becomes a specific FA-dispatch defect.
- **Not a regression bisect.** Neither fork's history was walked.
- **Not upstream-confirmed.** No genuine upstream binary exists on this node (C3).
- **The detector sees collapse, not quality.** Every "clean" above means "not degenerate",
  not "fidelity verified". A KLD panel is a different instrument.

## Script defect noted

`kv_xfork.sh`'s abort branch runs `grep -m2 -E "GGML_ASSERT|AllReduce"`, and the AllReduce
warnings appear *first*, so the printed excerpt showed the red herring and not the assert.
The assert was recovered by reading `srv_T7.log` directly. Fixed in `kv_xfork2.sh` by
grepping `GGML_ASSERT` alone.
