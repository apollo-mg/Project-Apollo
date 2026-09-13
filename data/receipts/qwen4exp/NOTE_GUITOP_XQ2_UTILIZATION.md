# Note — what `.194`'s per-card utilization shows during a Flash-Next request (X-Q2, 2026-09-13)

**Source:** an 11.07 s phone video of Mark's guiTOP dashboard (1920×1080, 30 fps), recorded 13:25:03–13:25:14.
guiTOP's own "Last update" clock is visible in every frame and agrees with the filename, so frames map to
`.194`'s driver log without guessing. Eight frames extracted at even spacing; six read. **The frames are
not committed** — they show room reflections — this table is the record.

**What was running:** arm **X-Q2** of `PREREG_FLASHNEXT_RESIDENCY.md` — UD-Q2_K_XL, `-ngl 99`, experts of
layers 44–47 on the CPU via `-ot`, `-sm layer`, one request. Its last request (3,600-token prompt) ran
prefill ≈ 13:24:43.0–13:25:08.5 (`prompt_ms` 25,492) and decode ≈ 13:25:08.5–13:25:15.1 (`predicted_ms`
6,656, 128 tokens).

| frame | guiTOP clock | phase | card 0 | card 1 | card 2 | card 3 |
|---|---|---|---|---|---|---|
| f0 | 13:25:03 | prefill | 0% | 0% | **63%** | 0% (187 W) |
| f1 | 13:25:05 | prefill | **56%** (143 W) | 0% | 0% | 11% |
| f2 | 13:25:06 | prefill | 0% | **100%** (172 W) | 0% | 0% |
| f3 | 13:25:07 | prefill | 0% | 0% | **33%** | 0% |
| f5 | 13:25:10 | decode | 20% (80 W) | 18% (79 W) | 18% (52 W) | 19% |
| f7 | 13:25:12 | decode | 24% (69 W) | 18% (43 W) | 18% (39 W) | 21% |

## Readings

- **One card works at a time, in both phases.** In prefill the busy card rotates (2 → 0 → 1 → 2) and the
  other three read 0%. In decode all four sit at 18–24%: the same hand-off, fast enough (~52 ms per
  token) that one-second sampling smears it into four partial bars. They sum to ~80%, so roughly a fifth
  of each token is time no card is working — hand-offs, the CPU-resident experts, sampling.
- **Layer split with one request makes the four P100s a relay:** four cards' memory, one card's compute.
- **Card 0 runs slightly hotter in decode (20–24% vs 18%)**, consistent with it carrying the non-layer
  tensors (the ~0.9 GiB extra measured on 08-28), including the 248,320-vocab output head.
- **Card 3's VRAM gauge sits visibly lower** — the `-ot` placement: 11,815 MiB in F-Q2 → 7,975 in X-Q2.
- **A two-frame reading was wrong and is recorded as such.** f0 and f3 alone showed card 2 busy both times
  and suggested card 2 was a slow stage. f1 and f2 show the busy card rotating. There is no single slow card.

## Why prefill cannot overlap here — and the check it points to

llama.cpp can overlap ubatches across cards in prefill (pipeline parallelism). buun `da458765d`,
`src/llama-context.cpp:589`:

```cpp
bool pipeline_parallel =
    model.n_devices() > 1 &&
    model.n_gpu_layers() > model.hparams.n_layer_all &&
    model.split_mode() == LLAMA_SPLIT_MODE_LAYER &&
    cparams.offload_kqv &&
    !model.has_tensor_overrides();
```

**X-Q2 carries a tensor override and P-Q2 is not fully offloaded, so both run with it off by design** —
which is the one-card relay filmed here. **F-Q2 (fully resident, no overrides) meets every condition**, yet
its prefill (131.0 / 144.4 / 104.5 tok/s at 500 / 1,800 / 3,600) is no better than X-Q2's (141.4 / 128.9
/ 141.2). So it is either not engaging or not helping. **Check:** the post-Stage-1 verification reload
(Amendment 2, item 2) runs each arm's exact command at higher verbosity; it should also record whether
the context reports pipeline parallelism enabled for F-Q2. If it is off for an incidental reason, it is the
only prefill lever found so far — residency did not move prefill.
