Reproduces on RDNA4, so that's a second AMD architecture. I also think I can name the exact case
that aborts.

**gfx1201 / RX 9070 XT, ROCm 7.2.53211**, sclk 1531 MHz / mclk 1258 MHz.

```
GGML_CUDA_DISABLE_GRAPHS=1 test-backend-ops -o FLASH_ATTN_EXT
  10,128 cases run, then SIGABRT (exit 134), core dumped
  ggml/src/ggml-cuda/fattn-tile.cu:65: Unsupported head size
```

Graphs are off on purpose — gfx1201 also hits the ROCm capture abort from #251 in this same
suite, and with graphs on I can't tell the two apart. With them off, the head-size abort is the
only one reachable.

`-p 'hsk=576'` narrows it from 10,128 cases to **16**.

## Naming the aborting case

The descriptor doesn't print, for the reason you noted on #251 — it's emitted after the verdict.
But `support` mode over the same filter recovers it, because that mode prints every case whether
or not it's supported.

Over `-p 'hsk=576'`, `support` reports **256 cases: 208 NOT SUPPORTED, 48 SUPPORTED**. Case
**17** is the first to claim support. `test` mode printed exactly **16** cases before dying, and
its last printed line is byte-identical to case 16 of the support listing. So the abort lands on:

```
FLASH_ATTN_EXT(hsk=576,hsv=512,nh=1,nr23=[4,1],kv=512,nb=1,mask=1,sinks=1,
               max_bias=0.000000,logit_softcap=0.000000,prec=f32,
               type_K=f16,type_V=f16,permute=[0,1,2,3])
```

`supports_op()` says SUPPORTED for that shape. `fattn-tile.cu` then aborts on it with
*Unsupported head size*.

That trick should generalise to any abort with this shape — `support` mode gives you the name
`test` mode can't.

## The 48 that claim support share a signature

```
kv=512  AND  mask=1  AND  nr23 != [1,1]          48 of 256

  kv=113      0/48        kv=1024   0/48        kv=512   48/160
  mask=0      0/72        mask=1   48/184
  nr23=[1,1]  0/160       nr23=[4,..] 32/64     nr23=[20,..] 16/32
  spread evenly over nb (12 each) and sinks (24/24); all prec=f32, all permute=[0,1,2,3]
```

So it isn't the head size alone — the same hsk=576/hsv=512 pair is correctly declined in 208
configurations and accepted in 48. The support predicate looks like it's advertising head sizes
the tile kernel doesn't implement, for the masked GQA-broadcast kv=512 slice specifically.

If that reading is right, the fix is in whatever makes `supports_op()` say yes there, and the
abort is reachable from any caller that trusts it — not only from this suite.

## Small #242 note

That `support` run ends with:

```
  Backend ROCm0: OK
2/2 backends passed
OK
```

Clean OK for a shape family that aborts the moment `test` mode evaluates it. Not the same bug as
#242, but the same flavour: the verdict reflects the probe completing, not the kernel working.

## Caveats on my build

`c26cbdffc`, which is **687 commits behind** `feature/turboquant-kv-cache` (`2f2f32f5d` when I
ran this). I checked it's representative for this path before reporting — `fattn-tile.cu`'s abort
moved line 65 → 64 with one unrelated deletion and nothing else. It's not a current-code claim
about anything beyond that.

Same sha is the one named in #252 for the turbo4 V-cache regression, so don't read anything into
this build's turbo4 behaviour.

K=1, but deterministic: the abort reproduced on the full sweep and the narrowed run, and the
support matrix is stable. Unlike the #251 capture abort, which wandered ~6× in
cases-before-abort across runs.

Happy to paste the full logs, the 16-case repro, or the 256-case support matrix if useful. I can
also re-run any of this on a current build — it's about 20 minutes.
