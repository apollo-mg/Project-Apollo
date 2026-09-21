Follow-up on #134 with the DFlash2 sidecar added, so this run matches your setup on 3 of 4
components -- only the NVFP4 weights are unmatched, since those need Blackwell.

**Short version: your budget-clamp message reproduces exactly. The abort does not. And I think
they may be two different problems.**

**Setup**

`.194`, 2x Tesla P100 (sm_60) of 4, Linux, CUDA 12.4, buun `08826ad6`. Qwen3.8-27B-Q6_K with the
external Q8 DFlash2 sidecar, resident vision projector, and your flags:

```
-c 200000 -ctk vbr -ctv vbr --vbr-entry t8 --vbr-floor t4 --ctx-checkpoints 2
-np 1 -sm tensor -fa on   --spec-type draft-dflash --draft-max 3
```

195,161-token prompt, single slot.

**Your clamp reproduces verbatim**

```
W prepare_with_slots: VBR budget 9472.00 MiB exceeded with the degrade order clamped at
  the --vbr-floor (projected 244.00 MiB at 8192 cells)
```

against your `VBR budget 11264.00 MiB exceeded with the degrade order clamped at the --vbr-floor`.
Same message, same precondition, on completely different hardware and OS.

**But it does not abort. It fails recoverably.**

```
W vbr_vmm_try_map: physical map of 540672 bytes failed at offset ... - flushing deferred unmaps and retrying
E prepare_with_slots: VBR VMM: physical map to N cells failed (device memory exhausted)
  - failing this batch recoverably
E srv decode: Context size has been exceeded.
```

HTTP 500 to the client, process still alive, no CUDA error anywhere in the log. I drove it to the
clamp twice, at two very different budgets, and both times it degraded cleanly instead of dying.

**Why I think these might be different failures**

Both are in `vbr-vmm.cu`, but at different call sites with different error classes:

| | mine | yours |
|---|---|---|
| call | `cuMemMap` / physical allocation | `cuMemSetAccess` |
| error | device memory exhausted | **device not ready** |
| handling | `return false` - the explicit recovery branch | `CU_CHECK` - abort |

`CUDA_ERROR_NOT_READY` is an async/stream state rather than an out-of-memory condition. The
exhaustion path has that `// physical exhausted -- caller decides (degrade / abort)` branch and it
works -- I hit it repeatedly. So I suspect #134 is not really "ran out of VRAM", which is roughly
how the issue reads at the moment. Offered as a hypothesis, not a diagnosis -- I never saw
`cuMemSetAccess` fail at all.

**Separate finding, and this one may matter for your own repro**

`[spec] auto-selected CUDA1 as the primary draft device` puts the **entire** 2.03 GB sidecar on one
GPU. Under tensor split the KV has to grow on both cards, so the tighter one gates the whole budget
while the other sits on unusable slack:

| split | GPU2 free | GPU3 free | binding | clamp at | failed at |
|---|---|---|---|---|---|
| default (even weights) | 3,443 MB | **341 MB** | 341 MB | **6,144 tok** | 22,528 tok |
| `-ts 57,43` (even free VRAM) | 2,279 MB | 2,589 MB | 2,279 MB | **122,880 tok** | 126,976 tok |

Same hardware, same model, same drafter, same flags -- only the weight distribution changed.
**20x later clamp and 6.7x more headroom on the card that actually decides.** So the real cost of
enabling an external drafter on a two-card tensor split is its full size, not half, because it all
lands on one side and nothing compensates the split for it.

You are also on two cards with an external DFlash2 sidecar, so it is worth checking whether your
11,264 MiB budget is capped the same way -- `nvidia-smi` right after load will show it immediately
if one card is about a sidecar fuller than the other. If it is, `-ts` tuned to even the free VRAM
rather than the weights might move your 174,827 abort point a long way, which would at least tell
you whether the abort tracks the budget or something else.

Might be worth auto draft-device placement informing the tensor split, or being split-aware.

**What I could not test**

NVFP4 weights (Blackwell), Windows, and CUDA 13.3 are all still unmatched, and any of them could be
the remaining variable. Neither of my runs completed the full 195,161 tokens -- the one that did,
yesterday, had no drafter at all.

Happy to run more: a lower `--vbr-floor`, more `--ctx-checkpoints`, or a build with logging added
around `vmm_pool_init` if you want to know whether that path is even live on Pascal.

*Posted by my agent (Claude Opus 5) on my behalf. The hardware and the runs are mine; I reviewed this before it went out.*
