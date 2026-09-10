# U2 + U3 — the forks share the *split* machinery and independently wrote the *kernels*

**2026-08-28.** Pure `diff` and `git`, no GPU. Compares `spiritbuun/buun-llama-cpp` @ `02f8581c6`
against `TheTom/llama-cpp-turboquant` `feature/qwen4exp` @ `3042c600b`.

## U3 — merge-base

Both forks are checked out as remotes in one repo on `.194`, so this is a direct computation, not
an inference:

```
$ git merge-base giveen/feature/qwen4exp buun/master
15586e2d7165570fb3aa7c26e0d442e289ef69de
  2026-08-06  Xuan-Son Nguyen: mtmd: add chunk save/load function (#26645)
```

**Common ancestor is upstream commit `15586e2d7`, 2026-08-06.** Divergence since:

| fork | commits since merge-base |
|---|---|
| Tom `feature/qwen4exp` | **294** |
| buun `master` | **1063** |

### A tag-based estimate would have been wrong

Tom's fork carries upstream-base tags up to `b10575`; buun's newest tag is `b9637` — ~940 builds
apart, which suggested buun was far behind. **The merge-base says otherwise**: both carry upstream
history through 2026-08-06. buun's tags are stale release markers, not a base indicator. Another
case of AFM-27 — a plausible signal read from the wrong layer.

## U2 — are the shared files identical?

**Split answer, and the split is the interesting part.**

| file | Tom lines | buun lines | changed lines | verdict |
|---|---|---|---|---|
| `ggml/src/ggml-backend-meta.cpp` | 2285 | 2324 | **135** (~6%) | **shared ancestry** |
| `ggml-cuda/fattn.cu` | 846 | **2685** | 2299 | **independent** |
| `ggml-cuda/fattn-common.cuh` | 1686 | 2192 | 1274 | **independent** |
| `ggml-cuda/fattn-vec.cuh` | 953 | — | 437 | divergent |
| `ggml-cuda/fattn-mma-turbo.cuh` | 118 | — | 222 | divergent |

Not whitespace or line endings — checked both (`diff -w` barely moves the count; neither file is
CRLF). buun's `fattn.cu` is **3.2x the size** of Tom's. buun also retains `fattn-wmma-f16.cu/.cuh`,
which Tom's tree no longer has.

The `ggml-backend-meta.cpp` differences are **additive features, not divergent logic**: Tom's side
carries the qwen4exp work (`cache_idx_*`, `cache_ple_r_*`, the undersubscribed-split policy), buun's
carries the DFlash rollback tape (`dflash_tape_*`). Confirmed separately today: the slice-assignment
loop inside `llama_meta_device_get_split_state` is **byte-identical** between the two forks, and
`get_split_granularity` differs only by those feature blocks.

## The synthesis — this reconciles U1 and XFORK

Two prior results looked in tension. They are not:

- **`RESULT_XFORK.md`**: the KV-collapse and split-axis abort reproduce **identically on both forks**.
- **U1**: the culprit `5fd308947` ("cuda : add TurboQuant MMVQ/WHT/inner-quant CUDA kernels",
  2026-07-31) is **Tom-only** — verified again today, `git merge-base --is-ancestor 5fd308947
  buun/master` is false. The forks hit it **independently**.

U2 explains how both can hold:

> The forks **share the tensor-split machinery** (`ggml-backend-meta.cpp`, ~94% common, byte-identical
> slice arithmetic) and **independently implemented the flash-attention / TurboQuant kernels**
> (`fattn*`, 3.2x size difference).

So a bug in the **split** layer reproduces on both because it is literally the same code, while a
bug in the **kernel** layer arose twice because two people solved the same problem separately. That
is exactly the pattern observed.

## Consequence for the outstanding reports

- Anything in `llama_meta_device_get_split_state` or the meta backend should be reported to **both**
  maintainers with the same patch — it will apply nearly verbatim. Today's zero-width-slice class is
  in this category.
- Anything in `fattn*` needs **separate diagnosis per fork**; a patch for one will not apply to the
  other, and a fix landing in one says nothing about the other.
- The `TURBO_AUTO_ASYMMETRIC` guard is **Tom-only** (`grep -c` = 0 in buun's tree) — see
  `RESULT_N9_TURBO3_AUDIT.md`.

## Status

**U2 and U3 answered.** U1-old's bisect range, if ever needed, is bounded below by `15586e2d7`
(2026-08-06) — but U1 is already resolved, so the bisect is likely moot.
