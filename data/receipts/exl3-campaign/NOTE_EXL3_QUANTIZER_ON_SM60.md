# Note — can we make our own EXL3 quants on Pascal? (ledger O8, source reading only)

**2026-09-12. No code was run.** This is what `turboderp-org/exllamav3@master` says, read from the public
repo. It is a sampling, not a verdict.

## What the project states

- **PyTorch with CUDA 12.4 or later** (README). The fleet is on CUDA 12.4, so that floor is met.
- **The quantizer is `convert.py -i <in> -o <out> -w <work> -b <bitrate>`,** and the working directory
  needs room for a full copy of the model.
- **Multi-GPU splits the trellis encoding** across devices; one linear layer per GPU when a layer has
  enough tensors (`doc/convert.md`). Neither the README nor the conversion guide states a compute
  capability.
- **`setup.py` sets no architecture gate.** It builds through torch's `cpp_extension`, so the extension
  compiles for whatever architecture torch targets locally.

## What the sampled kernels use

- **`quant/codebook.cuh`** uses `half2` intrinsics (`__hfma2`, `__halves2half2`). **Pascal supports these
  natively** — sm_60 has 2:1 fp16. It also carries one `__CUDA_ARCH__ == 860` branch for integer MAD,
  which is a special case, not a requirement.
- **`exl3_lib/quantize.py`** allocates `torch.half` and `torch.short` buffers and reads
  `torch.cuda.get_device_properties`. Its `tensor_core_perm` is an index permutation, not a tensor-core
  operation.
- **Not found in what I read:** bf16, `mma.sync`, `cp.async`, or an sm_80 floor.

**Sampled:** `setup.py`, `README.md`, `doc/convert.md`, `quant/comp_units/exl3_comp_unit_1.cuh`,
`quant/codebook.cuh`, `exl3_lib/quantize.py`. **The repo has 113 CUDA sources; most were not read.**

## Why this is not an answer

- **Sampling.** A single Ampere-only intrinsic in an unread kernel would decide it.
- **Torch's own support matters as much as exllamav3's.** Recent PyTorch wheels have been dropping older
  architectures, and one bf16 operation anywhere in the pipeline fails on sm_60.
- **The extension compiles at install time,** so a build error is as likely as a runtime error.

## The decisive test, about an hour

1. A venv on `.73` with a torch build that still supports sm_60, on CUDA 12.4.
2. Install exllamav3 and let its extension compile.
3. Convert `Qwen3-0.6B` at 4.0bpw with `convert.py`.
4. Load the result in buun's fork and compare its perplexity against turboderp's own 0.6B EXL3, which
   measured **20.2864** on `.73` (`kv-tensor-split/RESULT_EXL3_SM60_INFERENCE.md`).

**Cost:** roughly 3 GB of downloads, one compile, and the conversion. **Blocked on nothing but time.**
A pass would answer O8 and O9 together: we could quantize any model we can download, instead of waiting
for someone to publish an EXL3 of it.
