# N2 — buun's tensor-split behaviour varies by commit, and only one of three fails silently

**2026-08-18**, `.194`, quad Tesla P100 (sm_60), two GPUs selected to match `.73`'s topology.
Model `Qwen3.8-27B-Q6_K` (byte-identical size to `.73`'s). All arms `-sm tensor -ts 1,1`,
`TURBO_AUTO_ASYMMETRIC=0`, **`GGML_CUDA_ALLREDUCE=internal`** (see the NCCL note in
`RESULT_OWNERSHIP.md` — without it every arm dies, including the f16 control).
Raw `~/kv194/`, script `kv_194.sh`.

## Three buun commits, three behaviours

| commit | date | f16+f16 | `q8_0`+`q8_0` | `q8_0`+f16 | `q8_0`+turbo4 |
|---|---|---|---|---|---|
| `87c351d28` | 2026-06-03 | clean 3/3 | **abort `:757`** | abort `:757` | **abort `:757`** |
| `a8e5b5a38` | *(undated — `.73`)* | clean | **SILENT COLLAPSE** | abort | **clean** |
| `02f8581` | 2026-08-07 | — | **abort `:753`** | abort `:753` | — |

The asserts are **buun-added**, and differ from upstream's:

| tree | assert |
|---|---|
| upstream `e8f19cc0` | `ggml-backend-meta.cpp:535` `ret.axis != GGML_BACKEND_SPLIT_AXIS_UNKNOWN` |
| buun `87c351d28` | `ggml-backend-meta.cpp:757` `src_ss[0].axis != GGML_BACKEND_SPLIT_AXIS_1` |
| buun `02f8581` | `ggml-backend-meta.cpp:753` `split_states_equal(src_ss[0], src_ss[2])` |

## The finding

**buun's fork carries its own split-state guards that upstream does not**, and on two of the
three commits tested they refuse quantized KV under tensor split outright. That reads as
deliberate defensive engineering: fail loudly rather than emit garbage.

**Only `a8e5b5a38` — the commit that happened to be on `.73` — fails silently.** It is also
the only one of the three that *permits* `q8_0`+turbo4, the "speed and correctness" pair.

So the natural reading is that `a8e5b5a38` sits on a branch or revision where those guards are
absent or relaxed, and the silent collapse is what the guards on the other commits exist to
prevent. **That is a much better message for buun than "your fork corrupts output":** his own
assertions already catch this, and the build in daily use here is the one that slips past them.

## Two things this does NOT establish

- **Commit ordering.** `a8e5b5a38` is **not resolvable** from `.194` — absent from all three
  buun trees there and from a full `git fetch --all` on `buun-llama-cpp`. It is likely local to
  `.73` or on an unfetched branch (the directory there is `buun_vbr`, suggesting a VBR branch).
  So whether it predates or postdates `87c351d28`/`02f8581` is **unknown**, and "regression"
  vs "outlier branch" cannot be decided from here. Dating it needs `.73` powered on.
- **Host is a confound.** `.194` is four P100s on Ubuntu 26.04; `.73` is two on Kubuntu. Two
  GPUs were selected and the AllReduce path pinned to match, but a host effect is not excluded.
  The clean test — `a8e5b5a38` on `.194` — is blocked by the fetch problem above.

## Also confirmed here

`q8_0`+turbo4 **aborts** on buun `87c351d28`. That pair is clean on `a8e5b5a38` and on Tom's
fork, and is the configuration recommended as the working "speed and correctness" answer in
`RESULT_TWO_KV_BUGS.md`. **That recommendation is commit-specific on buun's fork**, not general.
