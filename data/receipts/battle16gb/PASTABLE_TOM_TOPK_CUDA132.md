Heads-up on something you may be shipping to anyone building on a current toolkit. Not my finding and not something I can reproduce — passing it on because it lands on DS4-Flash prefill specifically, which is a model you've published numbers for.

**Source:** r/LocalLLaMA thread today (u/fragment_me), root cause credited to u/fairydreaming — *"Starting with 13.2 DeviceTopK is used for top-k instead of argsort, this turns PP rate to crap."* Reported as a 100–150 t/s swing in DS4-Flash prefill, with the workaround being a downgrade to CUDA 13.1.

**Where it lands in the fork.** `ggml/src/ggml-cuda/top-k.cu:6`:

```cpp
#ifdef GGML_CUDA_USE_CUB
#    include <cub/cub.cuh>
#    if (CCCL_MAJOR_VERSION >= 3 && CCCL_MINOR_VERSION >= 2)
#        define CUB_TOP_K_AVAILABLE          // -> DeviceTopK::MaxPairs
#    endif
#endif
```

CCCL 3.2 ships with CUDA 13.2, so the threshold matches the report exactly. Below it, top-k falls through to the argsort path (`:39-49`, `:73-98`). The file is near-identical to upstream `0fcb3760b` — the differences I can see are `CUDA_CHECK` wrapping and the argsort chunking — so this is inherited rather than fork-introduced, but the fork carries it either way.

The reason it seemed worth mentioning rather than assuming you'd seen it: DS4 routes top-k over a large expert count every token, so this sits directly on the prefill path, and your DGX Spark writeup leads with sub-second TTFT. If that box is on 13.2+, the number may be understating what the hardware does.

**What I can and can't say.** I verified the gate and the threshold from source, and confirmed my own DS4 measurements are *not* affected — the P100 node builds against `CUB_VERSION 200500` (CCCL 2.5, CUDA 12.4), well under 3.2, so it never takes the `DeviceTopK` branch.

I cannot reproduce the regression itself and won't be able to: **CUDA 13 dropped Pascal (sm_60)**, so the P100 box can't install a new enough toolkit, and the only sm_75 card here is a 6 GB 1660 Ti that can't hold an 82.5 GB model. So this is a source-verified pointer, not a measurement from me — the claim is only "the fork can take this branch on CUDA ≥ 13.2", not "I have seen it be slow."

If it does reproduce on your side, a version-gated preference for the argsort path would be a small change, though presumably one worth raising upstream rather than carrying as a fork patch.

Unrelated, while I'm here — I re-baselined my DS4 numbers on the P100 fleet with a proper drift-control arm and had to correct myself: a `--numa distribute` speedup I'd measured at +22.7% is actually **+13.6%**. The control reproduced (4.61 vs 4.58 t/s) but the treatment didn't (5.16/5.31 vs 5.62) — my original was K=1 and landed high. Same lesson as the capture-abort spread: within-arm stability was 0.5% and told me nothing about run-to-run reproducibility. Also turned up that `--numa distribute` makes the *cold* first response about 2× worse (1.13 vs 2.30 t/s, reproducible), so it's a throughput/latency trade rather than a free win.
