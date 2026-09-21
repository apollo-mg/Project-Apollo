# Result -- buun issue #134 does NOT reproduce on Pascal/Linux/CUDA 12.4

**2026-09-20, `.73`** (2x Tesla P100-PCIE-16GB, sm_60, CUDA 12.4, Linux), buun `08826ad6`.

Issue #134 reports a **deterministic** abort at prompt token **174,827**, three attempts running,
on RTX 5080 + 5060 Ti / **Windows 11 / CUDA 13.3**:

```
VBR budget 11264.00 MiB exceeded with the degrade order clamped at the --vbr-floor
CUDA error: device not ready; device=0; function=ggml_backend_cuda_vmm_pool_map;
  source=ggml/src/ggml-cuda/vbr-vmm.cu:169; statement=cuMemSetAccess
```

The reporter ruled out hardware and weights: fixed cache tiers reach ~169K fine, so it is the
**dynamic VBR / VMM / checkpoint interaction**.

## Result: clean to 195,170 tokens

```
COMPLETED in 2339s
prompt_n = 195170    prompt_ms = 2335992    cache_n = 0
failure signatures: 0        server alive after: yes
```

**Straight past 174,827 with no budget warning, no VMM error, no abort**, then generated coherent
text. ~83 tok/s average prefill, degrading from 103 to ~56 tok/s as attention cost grew.

## The pressure condition WAS reached -- this is not a sidestep

The obvious weakness in a negative result is never reaching the failing regime. We did:

| | value |
|---|---|
| entry tier | **t8** = 8 bits/value |
| floor | **t4** = 4.125 bits/value |
| **kv_bpv at completion** | **4.34375** |

**VBR walked essentially the entire degrade ladder** -- 8 bits down to 4.34, within **0.22 bits**
of the floor -- and handled it. Peak VRAM 15,629 / 16,384 MiB on GPU0, under 800 MiB free. The
reporter's budget was 11,264 MiB; ours was tighter, so the ladder was exercised harder, not less.

## Configuration

Matched: `-c 200000 -ctk vbr -ctv vbr --vbr-entry t8 --vbr-floor t4 --ctx-checkpoints 2 -np 1`,
single long prefill (~195K), vision projector resident (`mmproj-F16.gguf`), `-fa on`.
`VBR_ARTIFACT_CAPTURE store ready` confirmed at load, so the checkpoint machinery was live.

**Deliberately different, and both matter:**

- **Q6_K GGUF, not NVFP4 safetensors.** NVFP4 needs Blackwell; unreachable on sm_60.
- **MTP drafting, not an external Q8 DFlash2 sidecar.** No DFlash2 adapter on this fleet
  (obtainable if it becomes the deciding variable).

## The caveat that limits the claim

**It is not confirmed that the VMM pool path executed.** `ggml_backend_cuda_vmm_pool_map` is the
failing function, and nothing was logged about VMM either way. What is established from source:

- `vbr-vmm.cu` carries **no compute-capability gate** -- the path is not arch-excluded.
- VMM is selected per device by `CU_DEVICE_ATTRIBUTE_VIRTUAL_MEMORY_MANAGEMENT_SUPPORTED` under
  `#if defined(GGML_USE_VMM)`, not by architecture. Pascal supports CUDA VMM.
- The pool is initialised from `fattn.cu:1554`, and this run used `-fa on`.

So the path is **very likely live and very likely exercised**, but "likely" is the honest word.
Instrumenting `vmm_pool_init` with a log line would settle it, and that is the first thing to do
if this negative result is load-bearing for anyone.

## What it is evidence for

Every platform variable is inverted relative to the report -- **Pascal not Blackwell, Linux not
Windows, CUDA 12.4 not 13.3** -- and the VBR degrade ladder was driven nearly to its floor without
incident. That points away from the VBR/checkpoint *logic* being independently broken, and toward
either the platform (CUDA 13.3's VMM behaviour, or Windows) or one of the two unmatched components
(NVFP4 weights, DFlash2 sidecar).

It does **not** prove the logic is sound. A negative result on a different arch narrows the search;
it does not close it.

## Next, in order of cost

1. **Log VMM pool init/map** -- removes the caveat above for a one-line patch.
2. **Add a DFlash2 sidecar** on this fleet, re-run. Closes the larger of the two config gaps.
3. `--ctx-checkpoints` above 2, or a floor below t4, to push the clamp harder.
