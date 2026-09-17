# Prereg -- does SCALE's cuModuleGetFunction report missing symbols?

**Written 2026-09-17, before the probe was built or run.** Companion to
`PREREG_SCALE_MEMINFO.md`; same card, same SCALE install.

## Why this test

Avarok/atlas #1119 reports a second SCALE 1.7.1 defect on gfx1201, already worked around in
PR #1107 by validating the ELF symbol table before launch:

> `cuModuleGetFunction -> 0 (CUDA_SUCCESS)   handle=0x...`
> `cuLaunchKernel      -> 200 (CUDA_ERROR_INVALID_IMAGE)`

That is, looking up a kernel symbol that does not exist returns success with an unusable
handle, deferring the failure to launch time. NVIDIA's driver returns
`CUDA_ERROR_NOT_FOUND` (500) at lookup.

The memory probe established that the *other* #1119 defect survives into **SCALE 1.7.3**
unchanged. This asks the same question for this one. As before, a clean falsification is
worth more to Atlas than a confirmation: #1119's acceptance criteria call for retiring the
workarounds behind feature flags once a SCALE fix is verified.

## Why it matters beyond the bug report

Atlas dispatches kernels from a filesystem registry keyed
`kernels/<hw>/<model>/<quant>/`. A lookup that silently succeeds for a symbol that is not
there converts "this kernel was never built for your hardware" -- a clear, early,
actionable error -- into an opaque launch failure much later, with no name attached. On a
new target like gfx1201, where missing kernels are the expected state rather than the
exception, that is the difference between a bring-up you can debug and one you cannot.
It is also why their ELF-validation workaround exists at all.

## Method

Driver API, not runtime API. Compile a one-kernel module to a fatbin, load it with
`cuModuleLoad`, then look up two symbols:

- `probe_real_kernel` -- present in the module (control)
- a name that is definitely absent (the defect case)

Then attempt `cuLaunchKernel` on whatever handle the absent lookup produced. Grid and block
are 1x1x1 and the real kernel writes a single float, to keep any launch trivial.

**Risk note:** launching an invalid function handle on the card driving the desktop could in
principle hang the GPU. Atlas already observed this exact path returning
`CUDA_ERROR_INVALID_IMAGE` rather than hanging, i.e. it is rejected before dispatch, so the
risk is low. The launch is attempted once, not in a loop.

## Predictions

| id | prediction | falsified if |
|---|---|---|
| **P-C1** | control: lookup of the present symbol returns `CUDA_SUCCESS` with a usable handle, and launching it succeeds | lookup or launch of the real kernel fails |
| **P-C2** | **THE FORK.** Lookup of the absent symbol returns `CUDA_SUCCESS` (0), not `CUDA_ERROR_NOT_FOUND` (500) | it returns 500, or any other error, at lookup time |
| **P-C3** | the handle returned for the absent symbol is **non-NULL** (Atlas logged `handle=0x...`) | the handle is NULL |
| **P-C4** | launching that handle fails with `CUDA_ERROR_INVALID_IMAGE` (200) | it returns a different error, succeeds, or hangs |

P-C2 is the defect. P-C3 and P-C4 characterise its shape and are the parts most likely to
differ from Atlas's 1.7.1 observation even if P-C2 holds.

## Exploratory, not scored

Whether `cuModuleGetGlobal` has the same behaviour for absent globals. Recorded if it runs
cleanly, but no prediction is committed and it will be labelled exploratory in the result.

## Deliberately out of scope

The `cudaMemGetInfo` defect, covered by the companion prereg and already scored.
