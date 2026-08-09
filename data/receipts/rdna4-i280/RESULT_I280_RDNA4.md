# #280 on RDNA4 — reproduces, and `supports_op()` is not the broken part

**Issue:** TheTom/llama-cpp-turboquant **#280** — *"HIP: test-backend-ops FLASH_ATTN_EXT aborts
on unsupported head size instead of skipping."* Reported by @jasstrong on **gfx1100 (RDNA3)**,
ROCm 7.2.3. This is the **second AMD architecture**.

**Environment** (`environment.txt`): gfx1201 / RDNA4, ROCm **7.2.53211**, sclk 1531 MHz /
mclk 1258 MHz, `GGML_CUDA_DISABLE_GRAPHS=1`.

## 1. It reproduces

```
GGML_CUDA_DISABLE_GRAPHS=1 test-backend-ops -o FLASH_ATTN_EXT
  -> 10,128 cases run, then SIGABRT (exit 134), core dumped
  -> ggml/src/ggml-cuda/fattn-tile.cu:65: Unsupported head size
```

Same abort site as the RDNA3 report. Graphs were **disabled deliberately** so the only reachable
abort is the head-size one — that isolates this from the separate ROCm graph-capture abort on
gfx1201 (#251), which otherwise fires in the same suite.

## 2. Narrowed to 16 cases

`-p 'hsk=576'` reduces the repro from 10,128 cases to **16**. Last case printed before the abort:

```
FLASH_ATTN_EXT(hsk=576,hsv=512,nh=1,nr23=[1,1],kv=1024,nb=75,mask=1,sinks=1,
               max_bias=0.000000,logit_softcap=0.000000,prec=f32,
               type_K=f16,type_V=f16,permute=[0,1,2,3]): not supported [ROCm0]
```

The aborting case is the **17th** — unprintable, because the descriptor is emitted *after* the
verdict (the localisation limitation Tom already documented on #251).

## 3. The part that isn't in the issue yet: support and dispatch disagree

Same binary, same filter, `support` mode instead of `test` mode:

| mode | hsk=576 cases | outcome |
|---|---|---|
| `support` | **256 probed** | **all 256 `NOT SUPPORTED`**, backend verdict **OK**, exit 0 |
| `test` | 16 run | **SIGABRT** at `fattn-tile.cu:65` |

**`ggml_backend_supports_op()` is correct.** It declines every one of the 256 DeepSeek-MLA-shaped
cases. Something in the test/eval dispatch path calls the tile kernel anyway, on shapes the
backend has already refused.

That relocates the fix: **the support predicate does not need changing — the dispatcher needs to
honour it.** Which also means the abort is reachable from any caller that dispatches without
consulting `supports_op()`, not just this suite.

## 4. It is also a #242-class false green

In `support` mode the run probes 256 cases, supports **zero**, and prints:

```
  Backend ROCm0: OK
2/2 backends passed
OK
```

That is #242 (*"test-backend-ops reports OK when every case in an op is skipped"*) with a
concrete instance attached: a backend can be declared OK for `FLASH_ATTN_EXT` on the strength of
having supported none of it. Combined with #280's abort, the HIP backend has two independent
reasons why no meaningful FA coverage exists — one kills the run, the other passes it vacuously.

## Limits

- **Build is 687 commits behind** the branch head (`c26cbdffc` vs `2f2f32f5d`). Verified
  representative *for this path*: `fattn-tile.cu`'s abort moved line 65 → 64 with one unrelated
  deletion, nothing else. It is **not** a current-code claim about anything else.
- That same `c26cbdffc` is the sha named in **#252** as where turbo4 V-cache broke. Unrelated to
  FA head-size dispatch, but this build should not be cited for turbo4 behaviour.
- K=1. The abort is deterministic here (reproduced on both the full and narrowed runs), unlike
  the graph-capture abort on #251 which is stateful and varies ~6× in cases-before-abort.
- No fix attempted, no patch proposed — this is a reproduction receipt.

## Files

`fa_full_head.log` / `fa_full_abort_tail.log` (full sweep, middle elided — 10k lines),
`hsk576_test_mode.log` (the 16-case repro), `hsk576_support_mode.log` (all 256 NOT SUPPORTED +
OK verdict), `environment.txt`.
