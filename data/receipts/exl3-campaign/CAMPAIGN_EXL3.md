# Campaign — EXL3 on the Pascal nodes

**Opened 2026-09-12**, after `kv-tensor-split/RESULT_EXL3_SM60_INFERENCE.md`. Mark's framing: *work from
ground truth until we run out of reasonable reasons not to use it instead.*

**Scope — this is "EXL3 on the P100 nodes", not "EXL3 instead of GGUF."** In buun's fork, all of
`exl3.cu` is compiled out under HIP (`#if !defined(GGML_USE_HIP)`, line 29), and its entry points are
`GGML_ABORT("EXL3 is CUDA only")` stubs (lines 399–402). So the control plane cannot serve EXL3, and it
is the only always-on box. Every EXL3 deployment on this fleet runs on:

- **`.73`**, which sleeps. It takes 10 s to wake and 77–99 s from a cold request to its first completion.
- **`.194`**, which costs a 216 s cold boot and 218 W at idle.
- **NVIDIA's 580 driver branch**, the last that supports Pascal.

## Method

- **The ledger is a list of objections.** Every reason not to switch is an entry, and each entry has one
  status:
  - **RETIRED:** measured, and the objection does not hold.
  - **CONFIRMED:** measured, and it holds.
  - **OPEN:** the test and its cost are named.
  - **NOT RETIRABLE BY US:** it needs upstream work or money.
- **Each test gets its own prereg**, committed before the data it governs, as usual.
- **The campaign ends when every entry is settled:** retired, or confirmed or not retirable and
  accepted. Then the switch is Mark's call.

## Where we start (measured)

- **Weights:** turboderp `Qwen3.8-27B-exl3` @ 4.00bpw (`mul1` codebook, `head_bits 6`, `mtp_bits 4`).
- **Baseline:** the daily driver's Q6_K, the withdrawn unsloth upload `db81afd1e1`.
- **Hardware and build:** `.73`'s two P100s, buun `9ae8f0f40` plus our e8m0 guard.

| | EXL3 4.00bpw | Q6_K | ratio |
|---|---|---|---|
| perplexity, wikitext-2, 40 chunks | 5.9520 | 5.9195 | +0.55%, on 61% of the bits |
| decode, `-sm layer`, **MTP off** | 6.96 t/s | 7.81 t/s | 0.89× |
| decode, `-sm tensor`, **MTP off** | 11.26 t/s | 13.22 t/s | 0.85× |

**0.85× is not the deployment number.** The daily driver serves `-sm tensor` **with MTP** at
22.5–26.2 t/s (measured 2026-08-29). Against that, EXL3's MTP-off 11.26 t/s is **about 0.45×**. Until
MTP on EXL3 is measured, 0.85× does not travel without "MTP off" attached.

## The ledger

| # | objection | status | evidence, or the test that settles it |
|---|---|---|---|
| O1 | **Can't run on the control plane (HIP)** | CONFIRMED at source · NOT RETIRABLE BY US | See the scope note above. Still open: does current master *abort* or *route to CPU* on RDNA4? A ROCm build at `9ae8f0f40` (`/mnt/TG_2TB/Projects/buun-9ae8f`) will answer that; the older local ROCm binaries contain no EXL3 code at all. **Only an upstream HIP port retires it.** Mark offered buun RDNA4 testing at 15:01 on 2026-09-12. |
| O2 | **Loses MTP, the daily driver's 1.83×** | OPEN, **test 1** | The source makes it plausible. The `qwen35` importer reads `text_config.mtp_num_hidden_layers` (turboderp's config sets it to 1) and sets `nextn_predict_layers` (`llama-safetensors-qwen35.cpp:1363, 1485`). The snapshot carries 39 `mtp.*` tensors, EXL3-quantized. Test: `PREREG_EXL3_DROPIN.md`. |
| O3 | **Loses vision** | OPEN, **test 1** | turboderp ships 333 vision tensors, but buun's native vision loader is gated to `qwen4_exp` (`clip-safetensors.cpp:71`). The route is the daily driver's existing `mmproj-F16.gguf`. |
| O4 | **Doesn't compose with VBR KV** | OPEN, **test 1** | No EXL3 refusal exists in the KV cache code. Test 1 reads `kv_bpv` back from `/slots`. |
| O5 | **Slower** | PARTIAL | 0.85× matched with MTP off. Test 1 measures the deployment-matched number: EXL3 plus the daily driver's flags against the deployed binary plus Q6_K. |
| O6 | **Quality beyond one perplexity number** | OPEN | Perplexity is a single number on wikitext. Next come KLD against a higher-precision reference, then task accuracy, since the HumanEval+ harness exists. **turboderp's `kld_table.json` does not answer this:** every one of its 2,807 bit-steps across 401 tensors falls by exactly 3.2257×. That is a fitted allocation curve, not a measurement. The design is under "Design notes". |
| O7 | **Prefill and long context** | OPEN | Test 1 gives a first prefill number (one prompt of about 15k tokens). Long-context behaviour is a separate test. |
| O8 | **We can't make our own quants** | OPEN | There is no quantizer in buun's tree. Does exllamav3's converter run on sm_60? CUDA 12.4 meets its stated floor, but its kernels may need a newer arch. Read the source first. The answer decides whether we are only consumers of EXL3 or can produce it. |
| O9 | **Supply is limited to what someone else has published** | follows from O8 | If O8 fails, the campaign can only ever cover published quants. That is a per-model check on HF. |
| O10 | **Loads from spinning disk on `.73`** | environment, not format | `/mnt/models` (NVMe) has 9.9 GB free, and the EXL3 directory lives on `/mnt/HDD`. Load times are not comparable until it moves, and NVMe space is Mark's upgrade call. |
| O11 | **Build carries a local patch** | OPEN upstream | Any CUDA below 12.8 needs our 2-line e8m0 guard (`kv-tensor-split/PATCH_e8m0_cuda128_guard.diff`). Offering it upstream is Mark's call. |

## Design notes

- **KLD reference (O6).**
  - **Reference:** the Q8_0, pinned at `unsloth/Qwen3.8-27B-GGUF@4ca72078` (29,047,086,048 B,
    sha256-verified 2026-09-12, at `/mnt/TG_2TB/AI/Models/qwen38-27b-ref/`).
  - **It is a reference, not ground truth.** KLD against it measures distance from Q8_0. The comparison
    that matters, EXL3 vs Q6_K, is a difference between two distances to the same reference.
  - **Why not bf16:** bf16 is 55 GB and fits only on `.194`.
  - **Placement:** the Q8_0 does not fit `.73` with room for the batched-matmul pool (the 22.9 GB Q6_K
    already OOM'd there at `-sm layer`). The reference must be generated on the control plane (ROCm,
    partial offload) or on `.194`.
  - **Backend noise:** a ROCm-made reference scored on CUDA carries backend noise into both arms. **The
    KLD prereg must measure that floor.** Score the Q6_K against the reference on both backends; the
    difference is the floor. EXL3 can only be scored on CUDA.
- **Supply (O9).** Check what exists per model before designing around it.

## Order

1. **Test 1, drop-in** (O2, O3, O4, O5, and a first O7 number): one `.73` window, `PREREG_EXL3_DROPIN.md`.
2. **O1 load behaviour on RDNA4** with current master, once the ROCm build finishes. Takes minutes, on
   the control plane.
3. **O6 KLD**, with the backend-floor control.
4. **O8:** read exllamav3's conversion requirements.
5. **O6 task accuracy.**
