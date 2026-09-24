# Pre-registration -- S4: the VBR rate-distortion curve on Qwen3.8-27B / Pascal

**2026-09-24, before any run.** BACKLOG S4: "VBR has no fixed operating point; point comparisons against static codecs
are category errors ... Right instrument: fidelity vs achieved allocation across fill levels."

**Prior art checked:** `ledger_precheck.py "VBR rate distortion kv_bpv fidelity fill level"` -> receipts found:
- `kv-depth/RESULT_KV_DEPTH_MATCHED_ALLOCATION.md` (09-23): frozen VBR beat static q8_0 by 71 % at matched
  allocation and was bit-exact f16 before pressure. That was **Qwen3.5-9B on the RX 9070 XT (ROCm)**, three VBR
  budgets, one matched pair per codec, with an allocation gate that voided one of two tests.
- `vbr-fidelity/RESULT_VBR_FIDELITY.md` (08-25): VBR at 3.25 bpv matched CBR turbo3_tcq on a calibration panel (one
  matched point, 27B, P100).
- AFM-46 / `vbr-benchmarking-freeze`: unfrozen VBR can stick at its floor, so every VBR arm here is frozen.

**What this adds:** the 27B (daily-driver family) on **Pascal/CUDA**. A **curve** of six budgets with fixed,
pre-registered interpolation replaces single matched pairs, so no allocation gate can void a test. It also gives
KLD at `.73`'s real operating points.

## Instrument

- `.194`, **one P100 per arm** (`CUDA_VISIBLE_DEVICES=g`, four arms in parallel, 1063 MHz / 150 W),
  `GGML_CUDA_ALLREDUCE=internal`. Every arm has device count 1.
- buun `08826ad6e` `build_sm60_0920` `llama-perplexity`, `-ngl 99 -fa on -c 32768 -b 512 -ub 512`.
- Weights **`Qwen3.8-27B-UD-Q2_K_XL`** (9,828,981,664 B, identical in size to Unsloth's current file). The only
  27B that fits one 16 GB card with 32k of f16 KV. Weights are constant across arms; KLD is measured against f16 KV
  on the same weights, so this isolates the KV codec.
- Text: wikitext-2 `wiki.test.raw` (sha256 `173c87a53759e020...`, the kv-depth text). Scored positions 16,384-32,766
  of every chunk; per-position KLD via `TURBO_KLD_DUMP`.

**Arms (11 + reference):**
- `REF`: f16 K/V, writes the uint16 base.
- Static: `Q8` q8_0, `Q4` q4_0, `T4` turbo4, `T3` turbo3_tcq.
- VBR, all with `VBR_FREEZE=1`, `--vbr-floor t1`, `VBR_TRACE`. The budget is `--vbr-vram` plus `VBR_BUDGET_MIB`, set
  as a fraction *f* of the f16 KV buffer that `REF` logs:
  - `VF`: *f* = 2.0, never binds;
  - `V75`, `V55`, `V40`, `V29`, `V22`, `V16`: *f* = 0.75, 0.55, 0.40, 0.29, 0.22, 0.16.

  The fractions bracket every static codec's nominal size (q8_0 0.531, q4_0 0.281, turbo4 0.258,
  turbo3_tcq 0.203).
- **Allocation (x-axis):** static arms use the logged `KV buffer size`; VBR arms use the per-chunk maximum
  `mapped_bytes` from the trace, averaged over chunks (the kv-depth method).

## Predictions

| # | claim | test | conf |
|---|---|---|---:|
| R1 | VBR before pressure is f16-exact on CUDA/Pascal | `VF` KLD is exactly 0 at every scored position | 0.75 |
| R2 | VBR beats q8_0 at q8_0's allocation | interpolated VBR KLD < `Q8` KLD: mean, and in >= 8/9 chunks, exact sign-flip p < 0.05 | 0.70 |
| R3 | VBR beats q4_0 at q4_0's allocation | same test vs `Q4` | 0.65 |
| R4 | VBR beats turbo3_tcq at its allocation | same test vs `T3` | 0.50 |
| R5 | the VBR curve is monotone | mean KLD non-increasing in allocation across the six budget arms | 0.90 |

**Interpolation, fixed now:**
- For a static arm with allocation *a*, take the two VBR budget arms whose allocations bracket *a*.
- Per chunk, interpolate log(mean KLD) linearly in log(allocation). The paired statistic is interpolated VBR
  minus static, per chunk (9 chunks; minimum attainable p = 0.0039).
- If no two VBR arms bracket *a*, that test is **VOID**; it is not re-run with new budgets.

`T4` is a frontier point, not a test (it sits between `Q4` and `T3`).

**Reading:** R2-R4 true -> VBR's allocator advantage generalizes from 9B/ROCm to 27B/CUDA, and the curve locates
`.73`'s operating points (floor t4 = 4.125 bpv; 5.83 bpv observed at 128k). R1 false -> VBR's CUDA path is not f16
before pressure on Pascal. That matters more than any curve point, and it goes to buun first.

## Not established by design

One weights file (2-bit body; KV sensitivity could differ at higher weight precision), one text, 32k depth. Frozen
VBR is a test mode: the curve describes the allocator, not the live controller (see AFM-46).
