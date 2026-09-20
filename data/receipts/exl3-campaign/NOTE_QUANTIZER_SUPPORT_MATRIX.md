# Note -- who can actually MAKE a quant, per format and per hardware

**2026-09-20.** "Can you produce one yourself" is a first-class pro/con for any compression
format and is usually left out of comparisons. This is what is measured, what is read, and what
is still unknown, on this fleet.

## The matrix

| format | quantizer | runs on CPU | Pascal sm_60 (`.73`) | RDNA4 gfx1201 (desktop) | Apple silicon |
|---|---|---|---|---|---|
| **GGUF** | `llama-quantize` | **YES** | yes | yes | yes |
| **EXL3** | `exllamav3 convert.py` | no, needs a GPU | **BLOCKED** (see below) | **NO** -- CUDA-only | no |
| **MLX** | `mlx_lm.convert` | n/a | no | no | **yes, only** |
| **Bonsai ternary** | none published | -- | -- | -- | -- |

**GGUF's quantizer running on CPU is the single largest practical advantage any of these formats
has, and it is almost never listed as one.** Anyone with the safetensors and disk space can
produce one, on any machine, with no GPU at all.

## EXL3: what blocks each host

**Read from `turboderp-org/exllamav3` README, 2026-09-20:** CUDA 12.4 or later, `torch >= 2.6.0`,
wheels built **cp313**. **No mention of ROCm, HIP, or AMD anywhere.**

### RDNA4 (desktop, RX 9070 XT) -- NO

The hardware side is fine and better than expected:

```
torch 2.13.0+rocm7.2   available: True   device: AMD Radeon RX 9070 XT
arch list: [gfx900 ... gfx1030, gfx1100, gfx1101, gfx1102, gfx1103, gfx1200, gfx1201, gfx950, ...]
hipcc 7.2.53211, AMD clang 22.0.0git
```

**`gfx1201` is in torch's arch list and the GPU is visible to torch.** The blocker is purely that
**the quantizer is CUDA-exclusive.**

**Do not confuse this with buun's work.** buun ported EXL3 **inference** to HIP inside llama.cpp
(`da458765d`, confirmed working on gfx1201 -- `RESULT_EXL3_RDNA4.md`). The **quantizer** is a
separate project (`exllamav3`) with no HIP port. Inference support does not imply conversion
support.

### Pascal (`.73`, 2x P100) -- BLOCKED, and the real gate is still untested

| prerequisite | state |
|---|---|
| CUDA 12.4 | present |
| gcc-13 (12.4 hard-errors above 13) | present |
| Python | **3.14.4** -- exllamav3 ships **cp313** wheels |
| `python3-venv` / `ensurepip` | **not installed** |
| torch | **absent**; no venv anywhere on the box has it |
| Qwen3-0.6B base weights | absent |
| disk | 19 GB on `/`, 18 GB on `/mnt/HDD` -- tight but adequate for 0.6B |

**The decisive unknown remains unanswered:** does the CUDA torch wheel still ship **sm_60**
kernels? PyTorch has been trimming old architectures. `NOTE_EXL3_QUANTIZER_ON_SM60.md` found no
blocker in exllamav3's own source and flagged exactly this -- *"torch's own sm_60 support matters
as much"* -- and it is still the gate.

**Checking it needs a Python 3.13 environment first** (pyenv or deadsnakes), then:

```
python3.13 -m venv ~/exl3quant
~/exl3quant/bin/pip install torch --index-url https://download.pytorch.org/whl/cu124
~/exl3quant/bin/python -c "import torch; print(torch.cuda.get_arch_list())"
```

`sm_60` present -> proceed to a real 0.6B conversion. Absent -> **O8 resolves to CONFIRMED with a
named cause: PyTorch dropped Pascal, not exllamav3.** Either outcome is publishable.

## Why this matters for a format comparison

The "who can make one" column is a **gradient, not a checkbox**:

1. **GGUF** -- anyone, any machine, CPU only
2. **EXL3** -- needs an NVIDIA GPU, a recent CUDA, a matching Python, and a torch that still
   targets your architecture. **Four separate gates, and this fleet fails at least one on every
   host it owns.**
3. **MLX** -- needs Apple silicon. A hard hardware gate, but a simple one.
4. **Bonsai ternary** -- **no public quantizer at all.** You get what PrismML publishes.

That ordering is a real practical property and it cuts the opposite way from fidelity: the format
with the best measured fidelity-per-byte (EXL3, `RESULT_EXL3_COMPRESSION.md`) is also the one this
fleet cannot produce, while the format with the loosest labels (GGUF, 26% spread at IQ3) is the
one anyone can make.

## Status

- **O8 remains OPEN**, but the blocker is now specific and named: a Python 3.13 environment on
  `.73`, then the torch sm_60 check.
- **RDNA4 quantization is CLOSED for EXL3** unless someone ports the quantizer to HIP.
