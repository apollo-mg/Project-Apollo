# sm_60 (Tesla P100 / GP100) — State of Support in llama.cpp CUDA

**Date:** 2026-07-12. Read directly from stock ggml-org/llama.cpp master `4f37f5197`
(`ggml/src/ggml-cuda/`), on the heels of the FAST_FP16 carve-out
(buun PR #80, turboquant PR #212). Every claim below is from source, not docs or vibes.

## 1. What the silicon has (and doesn't)

| capability | GP100 (sm_60) | notes |
|---|---|---|
| fp32 | 9.5 TF, full rate | the workhorse post-carve-out |
| fp16 arithmetic | 2:1 rate (18.7 TF) | unique among Pascal; the trap that caused the bug |
| **DP4A (int8 dot)** | **ABSENT** | introduced in sm_61 (GP102/104/106); GP100 missed it by one minor version |
| tensor cores | none | first appear sm_70 |
| cp.async | none | sm_80+ |
| HBM2 bandwidth | 732 GB/s | its enduring superpower; more than a 4080 (717 GB/s), ~73% of a 4090 |

## 2. What llama.cpp actually dispatches on sm_60 (verified in source)

**Flash attention: YES, it exists and works.** Contra the Python ecosystem (FA2 library
requires sm_80; community forks reach sm_70), llama.cpp has its own FA implementation with a
non-tensor-core path. `ggml_cuda_get_best_fattn_kernel` (fattn.cu) on sm_60 selects:
- **vec kernel** — decode (batch ≤ 2 with quantized KV, batch 1 otherwise)
- **tile kernel** — everything else (all of prefill)
Both were fp16-arithmetic until the carve-out; both are now fp32 with measured zero speed cost
and median-KLD 0.0023 → 0.000001. No port needed — Pascal FA is already here and now clean.

**Quantized-weight prefill: dequantize + cuBLAS GEMM — NOT MMQ.**
`ggml_cuda_should_use_mmq` (mmq.cu:267) returns false when
`highest_compiled_arch < GGML_CUDA_CC_DP4A (610)`, and that check precedes the
`GGML_CUDA_FORCE_MMQ` override — **MMQ is hard-off on sm_60 and cannot be forced on.**
The GEMM compute type is chosen by `fast_fp16_hardware_available` (carve-out gate #3):
fp16 before the patch (quality tax, Cell 0), fp32 after (measured: free).

**Decode (batch 1, quantized weights): mmvq**, whose int8 dot goes through
`ggml_cuda_dp4a` (common.cuh) — on sm_60 that's a **byte-wise emulation**
(`a8[0]*b8[0] + …`, compiles to IMAD sequences). Works, integer-exact, just not the
single-instruction path sm_61+ gets.

**f16-weight matvec: mmvf**, arithmetic type selected by `fast_fp16_available`
(carve-out gate #2) — fp32 post-patch.

## 3. Concrete opportunities (ranked, for anyone with Claude-time to burn)

1. **MMQ-on-sm_60 experiment** — the most interesting open question. The DP4A gate predates
   any measurement on GP100 as far as we can tell (same "assume, don't measure" vintage as
   FAST_FP16). MMQ avoids materializing the dequantized weight matrix, trading bandwidth for
   integer ALU — and P100 has 732 GB/s HBM2 *and* full-rate IMAD. Experiment: delete the
   arch check (or move it below FORCE_MMQ), build arch-60, llama-bench pp8192 vs stock.
   If emulated-dp4a MMQ beats dequant+cuBLAS on HBM2, that's a real Pascal speedup upstream
   left on the table. If it loses, the gate earns its keep and we've measured why. Either
   way: one line, one build, one bench.
2. **Tile-kernel occupancy tuning for GP100** — the tile FA kernel is generic across
   non-tensor-core NVIDIA. GP100: 56 SMs, 64KB smem/SM, 2:1 fp16 now unused. Nobody has
   profiled tile-kernel occupancy on sm_60 specifically (nsight-compute on a P100 rig would
   answer it in an afternoon). Speed-only, zero quality risk post-carve-out.
3. **sm_62 (Jetson TX2) carve-out measurement** — shares GP100's gate treatment (was on the
   FAST_FP16 path pre-patch, unlike exempted sm_61) and nobody has KLD-measured it. Anyone
   with a TX2: the killer-test recipe is fully documented and takes one evening.
4. **NOT worth doing: porting Python FA2 to sm_60.** llama.cpp's tile kernel already
   delivers working, now-numerically-clean FA on Pascal. The Python/Torch gap is real but
   it's an ecosystem problem (vLLM, training stacks), not a kernel-existence problem —
   and a much bigger lift than one contributor's spare month.

## 4. Training/Python-world reality check (brief)

FA2 library: sm_80+. V100 forks: sm_70. P100 training: ecosystem-abandoned (torch AMP
assumes tensor cores; bitsandbytes gates on sm_75+ for most paths). Pascal's lane in 2026
is inference — where llama.cpp, post-carve-out, is arguably the best-supported path it has.

## 5. Receipts

- FA dispatch: `fattn.cu` `ggml_cuda_get_best_fattn_kernel` (tensor-core branches all gate
  on `turing_mma/volta_mma/wmma`; sm_60 falls through to vec/tile).
- MMQ gate: `mmq.cu:267` `ggml_cuda_should_use_mmq`.
- DP4A emulation: `common.cuh` `ggml_cuda_dp4a`, `GGML_CUDA_CC_DP4A 610`.
- Carve-out quality/speed numbers: `Pascal_FAST_FP16_Carveout_Results.md` (panel receipts
  on .194).
