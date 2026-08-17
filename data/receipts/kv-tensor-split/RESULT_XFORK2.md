# Cross-fork KV, ladder 2 — the abort is tensor-split-specific, the collapse is not

**2026-08-17**, `.73`, dual P100 (sm_60). Binary **TheTom `f6124e9`** except U8
(**buun_vbr `a8e5b5a38`**). Model `unsloth-Qwen3.8-27B-Q6_K.gguf` (D=256, GQA 6:1),
`TURBO_AUTO_ASYMMETRIC=0` on every arm. Raw `~/xfork2/`, log `~/kv_xfork2.log`.
Follows `RESULT_XFORK.md`; script `kv_xfork2.sh`.

## Results

| arm | fork | K | V | split | outcome |
|---|---|---|---|---|---|
| U2 | Tom | `q8_0` | `q8_0` | tensor | **collapse 3/3** — control, reconfirms T2 |
| U4 | Tom | `q8_0` | `q4_0` | tensor | **HARD ABORT** `:535` |
| U5 | Tom | `q4_0` | `q8_0` | tensor | **HARD ABORT** `:535` |
| U7 | Tom | `iq4_nl` | `iq4_nl` | tensor | **HARD ABORT** `:535` |
| U9 | Tom | turbo3 | turbo3 | **layer** | **clean 3/3** |
| U8 | **buun** | `q8_0` | `q8_0` | tensor | **collapse 3/3**, `top=[('/', 512)]` |
| U1 | Tom | `q8_0` | `q8_0` | tensor, `-fa off` | **VOID** — invalid config, see below |
| U3 | Tom | `q4_0` | `q4_0` | tensor, `-fa off` | **VOID** — same |
| U6 | Tom | `q5_1` | `q5_1` | tensor | **VOID** — harness defect, see below |

## 1. N7 closed — buun emits the same character, not just the same statistics

`RESULT_XFORK.md` had to qualify the cross-fork claim: the buun run recorded
`len=512 maxrun=512 uniq=1` but never saved a response body, so the `/` was verified on
Tom's fork only. U8 re-ran that arm against `buun_vbr` with bodies retained.

**buun's fork emits 512 `/` characters**, identical `finish_reason=length`, first request,
deterministic 3/3. Same character, same count, same determinism, on two independently
maintained forks. There is no longer a reading in which these are two similar-looking bugs.

## 2. The two bugs separate on a *property*, not just a symptom

| | `-sm tensor` | `-sm layer` |
|---|---|---|
| `q8_0` symmetric | collapse | **collapse** (`RESULT_XFORK.md` T9) |
| turbo3 symmetric | abort | **clean** (U9) |

**The abort requires tensor split. The collapse does not.** This is the first evidence that
separates them by mechanism rather than by how they present, and it retroactively supports
the original "two distinct bugs" framing in `RESULT_TWO_KV_BUGS.md`.

> **QUALIFIED 2026-08-17, same day.** "The collapse does not [require tensor split]" is true
> of the **27B** — T9 here and F2 in `RESULT_FA_AND_GRID.md` both collapse 3/3 under layer
> split. It is **false for Qwen3.5-4B-BF16**, which is clean under layer (`kv_final.sh` M2)
> and collapses under tensor (`kv_4b.sh` Q2), same fork and node.
>
> So split-independence is **model-dependent**, not a property of the collapse. Every
> cross-binary comparison must therefore match split mode explicitly — one in
> `RESULT_UPSTREAM.md` did not, and is corrected there.

It also puts the abort where the assert already said it was — the split-axis resolver in
`ggml-backend-meta.cpp`. Under layer split there is no axis to resolve and the failure
disappears.

**Practical consequence:** honest turbo3-symmetric measurement on Pascal *is* possible —
use `-sm layer` with `TURBO_AUTO_ASYMMETRIC=0`. It costs the 1.62x tensor-split speedup, but
the number describes the codec that was requested. Under `-sm tensor` there is no such route:
guard on silently substitutes `q8_0` K, guard off aborts.

## 3. Three outcome classes, by codec pair (all under `-sm tensor`)

| class | pairs |
|---|---|
| **clean** | f16+f16 · `q8_0`+f16 · f16+`q8_0` · `q8_0`+turbo4 |
| **collapse** | `q8_0`+`q8_0` · `q4_0`+`q4_0` |
| **abort** | `q8_0`+`q4_0` · `q4_0`+`q8_0` · turbo3+turbo3 · `iq4_nl`+`iq4_nl` |

N5 asked whether the collapse trigger is "both stock" or "both the *same* stock type".
**Neither.** Mixed stock types (`q8_0`/`q4_0`) do not collapse and do not run — they abort,
symmetrically in both orders. "Both stock quantized" was too coarse a predicate.

**Hypothesis, explicitly not established:** the split-axis resolver supports a narrow set of
KV types. `q8_0`/`q4_0` symmetric resolve an axis and then produce garbage; `iq4_nl` and
turbo3 cannot resolve one and assert. Under this reading collapse and abort are two stages of
one gap in type support. **An earlier version of this hypothesis — that mismatched block
widths cause the abort — is already dead**: `iq4_nl`+`iq4_nl` and turbo3+turbo3 are same-type
pairs and both abort.

## 4. `-sm tensor` requires `-fa on` — the FA test cannot run under tensor split

U1/U3 are void, and the reason is a finding in its own right:

```
E llama_init_from_model: SPLIT_MODE_TENSOR requires flash_attn to be enabled
```

Not a quantized-KV constraint — a split-mode one. The flash-attention localisation test
therefore moves to layer split, where `-fa off` is legal and `RESULT_XFORK.md` T9 supplies
the matched control (`-sm layer -fa on`, `q8_0` symmetric → collapse 3/3). Run as `kv_fa.sh`.

## 5. Harness defect — U6 measured nothing and would have been a false finding

U6 (`q5_1` symmetric) reported `SERVER DIED`. The cause was not the codec:

```
E srv start: couldn't bind HTTP server socket, hostname: 127.0.0.1, port: 8092
```

U5 had just hard-aborted with a core dump and still held port 8092 when U6 launched; the
fixed `sleep 5` between arms was not enough. Reported naively this would have entered the
record as **"`q5_1` fails to start"** — a codec finding manufactured entirely by the harness.

The tell was log length: 9 lines for U6 against 64 for the genuine U7 abort. A real codec
failure has a model load in front of it.

This is the `AFM-1` family inverted — not a server wrongly declared *ready*, but a startup
failure wrongly attributed to the *thing under test*. **Corrective:** wait for the port to
actually be released rather than sleeping a fixed interval (`port_free()` in `kv_fa.sh`), and
sanity-check log length before accepting any negative result. U6 and U7 are both re-run as
`kv_fa.sh` F5/F6 — U7 is very likely genuine (64-line log, real assert, no bind error) but
it ran directly after the failed U6 and inherits the doubt.

## Calibration note

Three of the nine arms produced **"does not run"** outcomes. `AFM-16` was written this
morning precisely to stop under-weighting that branch, and the U4 prediction did list it
explicitly — at **0.10**, against clean 0.30 and collapse 0.60. It aborted.

So the correction is working at the level of *enumeration* and not yet at the level of
*probability*. In KV-codec configuration space on this hardware the running tally is now
**7 of 17 distinct configurations fail to run at all** — the "does not run" branch deserves
a prior near 0.3, not 0.1.
