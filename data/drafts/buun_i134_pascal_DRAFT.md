Tried to reproduce #134 on completely different hardware to see if it narrows things down for you.
**It does not reproduce.** Clean run to 195,170 prompt tokens, straight past your 174,827.

**Setup**

2x Tesla P100-PCIE-16GB (GP100, sm_60), **Linux, CUDA 12.4**, buun `08826ad6`. So every platform
variable is the opposite of yours: Pascal not Blackwell, Linux not Windows, 12.4 not 13.3.

Matched your flags:

```
-c 200000 -ctk vbr -ctv vbr --vbr-entry t8 --vbr-floor t4 --ctx-checkpoints 2 -np 1 -fa on
```

plus the vision projector resident, and one long single-slot prefill of ~195K tokens.

**Result**

```
COMPLETED in 2339s
prompt_n = 195170   cache_n = 0
no "budget exceeded", no cuMemSetAccess, no abort, server alive after
```

Then it generated normally.

**The degrade ladder was genuinely exercised, so this is not a sidestep**

That was my worry with a negative result, so I checked `/slots` at the end:

```
kv_bpv = 4.34375        (entry tier t8 = 8 bits, floor t4 = 4.125)
```

VBR walked from 8 bits down to 4.34, within 0.22 bits of the floor, and coped. Peak VRAM was
15,629 of 16,384 MiB with under 800 MiB free. Your budget was 11,264 MiB; mine was tighter, so if
anything the ladder got pushed harder here.

**Two things I could not match**

- **Q6_K GGUF instead of NVFP4 safetensors** -- NVFP4 needs Blackwell, so that is unreachable on
  Pascal.
- **MTP drafting instead of your external Q8 DFlash2 sidecar** -- I do not have a DFlash2 adapter
  on this fleet, though I can get one if it turns out to be the deciding variable.

**One caveat I want to be straight about**

I cannot confirm the VMM pool path actually executed, because nothing logs it either way. From
reading the source: `vbr-vmm.cu` has no compute-capability gate, VMM is selected per-device on
`CU_DEVICE_ATTRIBUTE_VIRTUAL_MEMORY_MANAGEMENT_SUPPORTED` rather than by arch, Pascal supports
CUDA VMM, and the pool is initialised from `fattn.cu` which this run hit with `-fa on`. So it is
very likely live and very likely exercised -- but "likely" is the honest word, and a log line in
`vmm_pool_init` would settle it in one build if this is load-bearing for you.

**What I think it is worth**

It points away from the VBR/checkpoint logic being independently broken, and toward either the
platform (CUDA 13.3's VMM behaviour, or Windows) or one of the two components I could not match.
It does not prove the logic is sound -- a clean run on a different arch narrows the search, it
does not close it.

Happy to keep going: add the VMM logging, get a DFlash2 sidecar, push `--ctx-checkpoints` higher
or the floor lower. Say which is most useful and I will run it.

*Posted by my agent (Claude Opus 5) on my behalf. The hardware and the runs are mine; I reviewed this before it went out.*
