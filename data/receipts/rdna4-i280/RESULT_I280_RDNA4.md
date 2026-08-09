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

## 3. `supports_op()` over-claims on a 48-case slice, and that names the aborting case

Same binary, same filter, `support` mode instead of `test` mode: **256 cases probed, 208
`NOT SUPPORTED`, 48 `SUPPORTED`.** The 48 that claim support share an exact signature:

```
kv=512  AND  mask=1  AND  nr23 != [1,1]        (48 of 256)
  kv=113   0/48      kv=1024  0/48      kv=512  48/160
  mask=0   0/72      mask=1   48/184
  nr23=[1,1] 0/160   nr23=[4,..] 32/64   nr23=[20,..] 16/32
  evenly spread over nb (12 each) and sinks (24/24); all prec=f32, all permute=[0,1,2,3]
```

**This names the case that `test` mode cannot print.** In support-mode ordering, case **17** is
the first to claim SUPPORTED. `test` mode printed exactly **16** cases before aborting, and its
last printed line is byte-identical to case 16 of the support listing. So the aborting case is:

```
FLASH_ATTN_EXT(hsk=576,hsv=512,nh=1,nr23=[4,1],kv=512,nb=1,mask=1,sinks=1,
               max_bias=0.000000,logit_softcap=0.000000,prec=f32,
               type_K=f16,type_V=f16,permute=[0,1,2,3])
```

`ggml_backend_supports_op()` says yes; `fattn-tile.cu` then aborts with *Unsupported head size*.
The inconsistency is inside the backend — the support predicate advertises head sizes the tile
kernel does not implement.

**Method note:** running `support` mode over the same filter recovers the descriptor that `test`
mode loses to the print-after-verdict ordering (#251). That works for any abort of this shape,
not just this one.

## 4. It is also a #242-class false green

In `support` mode the run probes 256 cases, and prints:

```
  Backend ROCm0: OK
2/2 backends passed
OK
```

That is adjacent to #242 (*"reports OK when every case in an op is skipped"*): here `support`
mode returns a clean **OK** for a shape family that provably aborts the moment `test` mode
evaluates it. The verdict reflects the probe completing, not the kernel working.

## Independently replicated on current HEAD, third architecture (2026-08-09)

@jasstrong reproduced all of it on **gfx1100 / RX 7900 XTX (RDNA3), ROCm 7.2.3**, and — closing
this receipt's own stated caveat — on **current `feature/turboquant-kv-cache` HEAD (`2f2f32f5d`)**,
not the 687-behind build measured here:

| claim made here | independent result |
|---|---|
| 256 probed, **208 NOT SUPPORTED / 48 SUPPORTED** | **same split** |
| first case claiming support (named above) | **byte-identical** |
| 16 cases print, then SIGABRT (134) | **same** |
| abort at `fattn-tile.cu:65`, *"moves to 64 on newer trees"* | **line 64** on current HEAD |
| `support` mode recovers the name `test` mode cannot print | **works there too** |

The build-vintage caveat was the right one to state and it is now discharged: the predicted line
shift 65 → 64 is exactly what a current-HEAD run reports. **The `supports_op()`-says-yes /
`fattn-tile` aborts mismatch on the masked GQA-broadcast `kv=512` slice is confirmed on current
code across RDNA3 and RDNA4.**

Also reported there: on gfx1100 the head-size abort is reachable with graphs *on* as well.
Disabling them keeps it isolated, which is why this receipt does so, but the abort is not
graph-dependent.

## Limits

- **Build is 687 commits behind** the branch head (`c26cbdffc` vs `2f2f32f5d`) — **discharged**
  by the independent current-HEAD replication above. Verified representative *for this path*: `fattn-tile.cu`'s abort moved line 65 → 64 with one unrelated
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
