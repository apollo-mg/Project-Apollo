# Known-good state snapshot — 2026-09-09

Recorded deliberately as **insurance**. `llama.cpp`/`ggml` maintainers moved to Hugging Face in
February 2026 and Hugging Face is being acquired by NVIDIA (announced 2026-09-02, closing H1 2027).
The code is MIT and cannot be retracted, but **the maintenance capacity is now employed by a company
that sells the competing silicon**, and forks depend on upstream churn that is already causing people
to abandon work (Jabba dropped `kvarn` this week over exactly that).

This file pins what currently works so a future rebuild is possible without depending on any
third party still hosting anything.

## Toolchain (control plane, RX 9070 XT)

| | |
|---|---|
| ROCm / HIP | **7.2.53211-3d9ef42** |
| ROCm path | `/opt/rocm` |
| GPU | RX 9070 XT, gfx1201, 16 GB |
| compiler | GNU 16.2.1 (per `llama-server --version`) |
| OS | CachyOS, kernel 7.2.2-1-cachyos |

## Engine checkouts (all local, full history unless noted)

| repo | commits | HEAD | upstream |
|---|---|---|---|
| `buun-llama-cpp` | 11,804 | `3823c9eb6` | spiritbuun/buun-llama-cpp |
| `llama_cpp_turboquant` | 9,971 | `c26cbdffc` | TheTom/llama-cpp-turboquant |
| `llama-cpp-turboquant-vulkan` | 9,418 | `2cbfdc62a` | TheTom/llama-cpp-turboquant |
| `llama_cpp_bonsai` | 10,068 | `9c46627bc` | ggml-org/llama.cpp |
| `llama-cpp-tq3` | 8,671 | `7552dfc3f` | turbo-tan/llama.cpp-tq3 |
| `prism_llama_cpp` | 8,194 | `1179bfc82` | PrismML-Eng/llama.cpp |
| `llama_cpp_gemma4` | 8,667 | `c08d28d08` | ggerganov/llama.cpp |
| `llama_cpp_latest` | 8,605 | `0fcb3760b` | ggerganov/llama.cpp |
| `llama-cpp-rdna4-tq3` | 6 | `273a160` | markldn/llama.cpp-rdna4-tq3 |

**`llama_cpp_turboquant` was SHALLOW and was un-shallowed on 2026-09-09** — it is Tom's fork, whose
future he describes as *"unplanned as of yet."* Now carries full history, 4 remote branches and
**6,215 tags**, including `tqp-v0.2.0` and the `feature-turboquant-kv-cache-*` tags a shallow clone
would have lost.

## Verified-working configurations

**`.73` (dual P100, sm_60) — `build_a56` @ `a56eeef51026b09210357526097bd4a2726f6473`**
Verified 2026-09-08: tensor-split prompt reuse restored (4,010 → 4 tokens on pass 2, **19.1×**),
artifact-store binding `lanes=2`. Best config measured:
```
-ngl 99 -c 32768 -np 1 -fa on --kv-unified -ctk vbr -ctv vbr --vbr-floor t2 --vbr-vram auto \
  --split-mode tensor --spec-type draft-mtp --jinja
```
DavidAU 40B IQ4_XS: **16.20 t/s**, MTP acceptance 0.865. `--split-mode tensor` is 1.26× layer **and**
retains prompt caching post-`a56eeef5`.

**9070 XT — buun `3823c9eb6`**
`Qwen3.8-27B-GSQ-RCO-IQ3_XXS-mtp`, 27.4 t/s no-MTP / 43–60 t/s with healthy MTP. 45–61% of the card's
640 GB/s theoretical bandwidth.

## Known defects in this state — do not lose these with the snapshot

- **VBR floor clamp kills MTP acceptance permanently** (`viability/RESULT_TIMEOUT_WALL_ROOT_CAUSE.md`).
  Clamp itself is benign; only harmful with `--spec-type` present. Restart restores it.
- **Server `-n N` does not bound generation** — 7/13 requests exceeded a 4,096 cap on a clean run.
- **RDNA4 FP8 is unreachable**: the HIP FP8 path is gated to `CDNA3` (`common.cuh:853`) and ggml has
  no FP8 weight type at all.
- **`GGML_CUDA_CC_IS_RDNA4` exists** but the arch-specific matrix paths in `mmf.cu` are CDNA-only.

## Remaining gap

**The engine clones exist only on this machine.** The Apollo repo tracks them as submodules — it
stores pointers, not code. If a fork is deleted upstream *and* this disk fails, the code is gone.
NAS (`//10.0.0.43/mgalyan`) has 2.7 TB free; mirroring the engine repos there is the obvious next
step and has not been done.

Models: 43 GGUFs, **404 GB** local, 1.3 TB free on TG_2TB. Hugging Face becoming NVIDIA-owned makes
local copies of anything load-bearing worth keeping rather than re-downloading on demand.
