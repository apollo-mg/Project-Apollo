# Result -- a drafter on one card silently costs 20x the KV budget; and #134's abort still does not reproduce

**2026-09-21, `.194`** GPUs {2,3} (socket-1 PHB pair, `numactl --cpunodebind=1 --membind=1`,
`GGML_CUDA_ALLREDUCE=internal`, 1063 MHz / 150 W). buun `08826ad6`, `Qwen3.8-27B-Q6_K`,
**external Q8 DFlash2 sidecar** (`--spec-type draft-dflash --draft-max 3`), **resident vision
projector**, `-c 200000 -ctk vbr -ctv vbr --vbr-entry t8 --vbr-floor t4 --ctx-checkpoints 2`,
`-np 1 -sm tensor -fa on`. Prompt 195,161 tokens from `wikitext-2-raw`.

Matches buun's #134 on **3 of 4 components** -- only NVFP4 weights remain unmatched (Blackwell
only). Yesterday's `.73` arm matched 2 of 4 and never reached his precondition at all.

## Finding 1 -- the drafter lands on ONE card and gates the whole KV budget

`[spec] auto-selected CUDA1 as the primary draft device` puts the entire 2.03 GB sidecar on one
GPU. Under tensor split the KV must grow on **both**, so the tighter card decides everything and
the slack on the other is unreachable.

| split | GPU2 free | GPU3 free | **binding** | clamp at | failed at |
|---|---:|---:|---:|---:|---:|
| default (even weights) | 3,443 MB | **341 MB** | **341 MB** | **6,144 tok** | 22,528 tok |
| **`-ts 57,43`** | 2,279 MB | 2,589 MB | **2,279 MB** | **122,880 tok** | 126,976 tok |

**6.7x more headroom on the card that matters, 20x later clamp, 5.6x further run.** Same
hardware, same model, same drafter, same flags -- only the weight distribution changed.

**The cost of enabling a drafter on a 2-GPU tensor split is roughly its FULL size, not half**,
because it all lands on one side and nothing compensates the weight split for it.

**Rule: with an external drafter on a 2-GPU tensor split, set `-ts` so FREE VRAM is even, not so
weights are even.** Mark's question ("does one card's pressure affect VBR degradation -- better to
force the split even?") is answered yes, and the effect is the largest single-flag win measured on
this fleet.

**Worth reporting upstream on its own:** auto draft-device placement should either inform the
tensor split or be split-aware. buun's own #134 setup is two cards (5080 + 5060 Ti) with an
external DFlash2 sidecar, so his 11,264 MiB budget may be capped the same way.

## Finding 2 -- the clamp reproduces; the abort does not

Buun's precondition reproduces **verbatim**, on Pascal/Linux/CUDA 12.4:

```
W prepare_with_slots: VBR budget 9472.00 MiB exceeded with the degrade order clamped at
  the --vbr-floor (projected 244.00 MiB at 8192 cells)
```

against his *"VBR budget 11264.00 MiB exceeded with the degrade order clamped at the --vbr-floor"*.

**But the server does not abort.** Both arms fail *recoverably*:

```
W vbr_vmm_try_map: physical map of 540672 bytes failed at offset ... — flushing deferred unmaps and retrying
E prepare_with_slots: VBR VMM: physical map to N cells failed (device memory exhausted)
  — failing this batch recoverably
E srv decode: Context size has been exceeded.
```

HTTP 500 to the client, process alive, no CUDA error. **So the clamp is NOT sufficient to cause
his abort.**

## The mechanism distinction, which is the actionable part

Both failures are in `vbr-vmm.cu`, but at **different call sites with different error classes**:

| | ours | buun's |
|---|---|---|
| call | `cuMemMap` / physical allocation | **`cuMemSetAccess`** |
| error | device memory exhausted | **`device not ready`** |
| handling | `return false` -> recoverable | **`CU_CHECK` -> abort** |

`CUDA_ERROR_NOT_READY` is **not an out-of-memory condition** -- it is an async/stream state. The
source has an explicit recovery branch for exhaustion (`return false; // physical exhausted --
caller decides`), which is the path we hit; `cuMemSetAccess` is wrapped in `CU_CHECK`, which is
the path he hits.

**Consequence: #134 is probably not "ran out of VRAM", which is how the issue currently reads.**
Driving the same subsystem to genuine exhaustion on different hardware produces a clean recoverable
failure, twice, at two very different budgets.

## What this does NOT establish

- **NVFP4 weights untested** and untestable here (Blackwell). Also untested: Windows, CUDA 13.3,
  Blackwell -- any of which could be the remaining variable.
- **No `cuMemSetAccess` failure was observed at all**, so this says nothing about why that call
  would return `device not ready`.
- `-ts 57,43` was computed to equalise free VRAM for *this* drafter and model; it is not a
  general constant.
- Both runs ended in failure, just far apart. **Neither completed 195,161 tokens** -- the `.73`
  arm yesterday did, without a drafter, which is the only clean full-length completion so far.
