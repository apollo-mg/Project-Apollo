# The FA question is unanswerable by flag, and the stock grid completes

**2026-08-17**, `.73`, dual P100 (sm_60). Binary **TheTom `f6124e9`**, model
`unsloth-Qwen3.8-27B-Q6_K.gguf` (D=256, GQA 6:1), `TURBO_AUTO_ASYMMETRIC=0` throughout.
Raw `~/xfork_fa/`, log `~/kv_fa.log`, script `kv_fa.sh`. Follows `RESULT_XFORK2.md`.

## Results

| arm | K | V | split | FA | outcome |
|---|---|---|---|---|---|
| F4 | f16 | f16 | layer | **off** | **clean 3/3** — admissibility gate |
| F1 | `q8_0` | `q8_0` | layer | **off** | **refused to start** |
| F2 | `q8_0` | `q8_0` | layer | on | **collapse 3/3** — matched control |
| F3 | `q4_0` | `q4_0` | layer | **off** | **refused to start** |
| F5 | `q5_1` | `q5_1` | tensor | on | **HARD ABORT** `:535` |
| F6 | `iq4_nl` | `iq4_nl` | tensor | on | **HARD ABORT** `:535` |

## 1. N4 is closed as unanswerable, not open

The plan was: if `-fa off` is clean while `-fa on` collapses, the defect localises to
flash-attention dispatch on sm_60. **That comparison cannot be constructed on this build.**

```
-sm tensor + -fa off  ->  E llama_init_from_model: SPLIT_MODE_TENSOR requires flash_attn to be enabled
-sm layer  + -fa off  ->  E llama_init_from_model: quantized V cache requires flash_attn to be enabled
```

Two independent constraints, and between them **the collapsing configuration only exists
with flash attention enabled.** There is no FA-off arm to compare against, so toggling FA
cannot isolate anything.

F4 rules out the boring explanation: `-fa off` itself works fine on this build under layer
split (clean 3/3 with f16). The refusal is specific to the *quantized V cache*, not to
`-fa off`.

The reachable neighbour — quantized K + f16 V with `-fa off` — is already clean *with* FA on
(`RESULT_XFORK.md` T4), so it carries no information about the collapse.

**Recorded as answered-negative rather than left open**, because the original framing was
never testable and leaving it in the backlog would invite someone to retry it. The mechanism
question now runs through **N1** (head-dim) or through a build with the fused path forced
off — not through a flag.

## 2. F2 is a same-session matched control, and it holds

`q8_0` symmetric under **layer** split collapses 3/3 with the same `/` signature. This
reconfirms `RESULT_XFORK.md` T9 within this run, so the F1 refusal cannot be attributed to
drift between sessions — the arm it would have been compared against was verified minutes
earlier on the same binary.

## 3. The stock grid, completed

F5/F6 re-ran the two arms `kv_xfork2.sh` lost: U6 (`q5_1`) was **void** to a port-bind race,
and U7 (`iq4_nl`) was legitimate but inherited doubt by running immediately after it. Both
re-ran behind `port_free()`; both are clean measurements this time (64-line logs, zero bind
failures, real asserts).

**`q5_1` aborts. `iq4_nl` aborts** — confirming U7.

Full map on Tom's fork at D=256, `-sm tensor`:

| outcome | pairs |
|---|---|
| **clean** | f16+f16 · `q8_0`+f16 · f16+`q8_0` · `q8_0`+turbo4 |
| **collapse** | `q8_0`+`q8_0` · `q4_0`+`q4_0` |
| **abort** | `q8_0`+`q4_0` · `q4_0`+`q8_0` · `q5_1`+`q5_1` · `iq4_nl`+`iq4_nl` · turbo3+turbo3 |

**Only `q8_0` and `q4_0` — the two oldest and simplest block formats — get far enough to
produce garbage.** Every other quantized symmetric pair asserts in the resolver.

## Hypothesis, explicitly not established

A two-layer reading fits most of the map: the split-axis resolver carries an effective
allowlist of KV types, and off-list types assert; *separately*, among on-list types, having
both K and V quantized yields garbage from the attention kernel. Collapse and abort would be
two different stages failing.

**It does not fit `q8_0`+turbo4, which is clean** — turbo4 is quantized, resolves, and pairs
with a quantized K without collapsing. Either turbo codecs take a different kernel path, or
the second layer's predicate is narrower than "both quantized".

Recorded as an open hypothesis with its own counter-example attached. `AFM-17` was written
this morning about exactly this failure — building a mechanism story from reading rather than
from execution — so it stays labelled until a test discriminates it.

## What this does NOT establish

- **Still one head dim.** Everything above is D=256. **N1** (`kv_d128.sh`,
  Llama-3.2-3B-Instruct-BF16, D=128) is the live test and is the only remaining route to a
  mechanism from this angle.
- **No fidelity claim.** "Clean" means not degenerate. The detector cannot see quality.
- **No upstream comparison.** Still no genuine upstream binary on the node (**C3**).
