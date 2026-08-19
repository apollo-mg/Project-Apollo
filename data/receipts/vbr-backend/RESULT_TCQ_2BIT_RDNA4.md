# The collapse needs three things at once: ROCm, a TCQ KV codec, and 2-bit weights

**2026-08-19.** Control plane **RX 9070 XT (gfx1201, ROCm/HIP)** and **`.194` single Tesla
P100 (sm_60, CUDA)**. Binary **buun `02f8581c65`** on both — same fork, same commit, only the
backend differs. Script `vbr_backend.py`, raw logs in `raw/`, predictions in
`PREDICTION_STATIC_TIERS.md` (all logged before their runs).

## The result

Collapse = every response is pure `!` to the token cap, HTTP 200, `finish_reason: length`,
and the server never recovers. Clean = normal answers, `finish_reason: stop`, canary alive
after the sequence.

### RX 9070 XT — ROCm

| model | weights | D | f16 | `q8_0` | `q4_0` | `turbo3_tcq` | `turbo1_tcq` |
|---|---|---|---|---|---|---|---|
| Llama-3.2-3B | BF16 | 128 | 9/10 | 9/10 | — | **9/10** | degraded* |
| Qwen3.5-9B | Q8_0 | 256 | 10/10 | — | — | **10/10** | **10/10** |
| Qwen3.8-27B | `AD-IQ2_S` | 256 | 9/10 | 9/10 | 9/10 | **COLLAPSE** | **COLLAPSE** |
| Qwen3.8-27B | `UD-IQ2_M` | 256 | 10/10 | — | — | **COLLAPSE** | — |

### Tesla P100 — CUDA

| model | weights | D | f16 | `q8_0` | `turbo3_tcq` |
|---|---|---|---|---|---|
| Llama-3.2-3B | BF16 | 128 | 9/10 | 9/10 | **9/10** |
| Llama-3.2-3B @ 64k ctx | BF16 | 128 | 9/10 | 9/10 | **9/10** |
| Qwen3.8-27B | `UD-IQ2_M` | 256 | 10/10 | 10/10 | **9/10** |

\* `turbo1_tcq` at D=128 gives coherent **wrong answers**, not `!` spam — a different failure.

## The decisive pair

`Qwen3.8-27B-UD-IQ2_M.gguf`, **md5 `7ba3d070fecfd7f1324b9e08887f5b8c` verified identical on
both machines**, same binary commit, same ten items, same flags:

| | `turbo3_tcq` |
|---|---|
| P100 / CUDA | **clean 9/10** |
| RX 9070 XT / ROCm | **COLLAPSE at item 1, canary dead after** |

## What each variable was shown to be

- **Not the backend alone.** At D=128/BF16 the two backends agree within **22 MiB** of
  allocation on every arm and return identical verdicts.
- **Not head dim.** Qwen3.5-9B at D=256 with 8-bit weights is clean on every TCQ tier,
  including the 1.25 bpv floor.
- **Not context depth.** The 3B at 65,536 ctx — 4× the allocation — is clean on CUDA.
- **Not quantized KV generally.** Stock `q8_0` **and** `q4_0` are clean on the very 2-bit
  model that TCQ collapses.
- **Not the checkpoint.** Two packagers' 2-bit quants (AtomicChat `AD-IQ2_S`, unsloth
  `UD-IQ2_M`) collapse identically on RDNA4.
- **Not the VBR controller.** `vbr` is the CLI alias for `turbo3_tcq`; driving the codec
  statically collapses the same way, first item, every time.

**All three conditions are necessary: gfx1201/ROCm + a TCQ KV codec + 2-bit weights.**

**Scope of the backend claim.** The arm that removes the backend was a **single Tesla P100,
sm_60, CUDA**. That establishes *not-on-sm_60*, which is not the same as *not-on-CUDA* — no
CUDA part with Turing MMA or newer was tested, and the fleet no longer contains one (the
1660 Ti was sold). The D=128 backend-equivalence cited above ran on **BF16 weights**, the
condition under which nothing fails on either device, so it cannot carry the 2-bit case.
Read this as **gfx1201 vs sm_60, one card each** — not as a vendor-level statement.

## Validity

Every arm records measured VRAM allocation (sysfs on amdgpu, `nvidia-smi` on CUDA), because a
codec that silently falls back to f16 produces a *clean* arm and would have faked the
CUDA result. Measured deltas track the bit-rate arithmetic: `turbo1_tcq` vs `turbo3_tcq` on the
27B differed by **131 MiB against 128 MiB predicted**; on the 3B, f16 → `q8_0` → `turbo3_tcq`
came in at 8,289 / 7,480 / 6,880 MiB against 1,792 / 952 / 364 MiB of predicted KV. No arm
fell back.

## Corrections to earlier receipts

- **`RESULT_VBR_COLLAPSE_CONTROLLED.md` attributed this to "the VBR KV path."** Too broad and
  pointed at the wrong component — the dynamic controller is not involved. It is the TCQ
  codec, and only under the two other conditions above.
- **A floor-tier hypothesis raised the same morning is dead.** The collapsed server's log
  showed KV priced at the `turbo1_tcq` 1.25 bpv floor (two projection figures decode to
  exactly 1.25 bpv plus the 128 KiB fixed overhead from `RESULT_U5E_KVSIZE.md`), which
  suggested the floor tier was the problem. The **nominal** 3.25 bpv tier fails identically,
  so the floor is not the explanation.

## Open

- **Untested on any CUDA part with MMA.** The only CUDA evidence is sm_60. An Ampere or
  newer card would decide whether this is an AMD-side defect or a low-bit-weight defect that
  Pascal happens to dodge. Nothing in the fleet can answer it.
- **Where between 2-bit and 8-bit does it start?** No mid-bit weight quant has been tested on
  RDNA4. With the desktop session live (13,749 MiB free) the ceiling is ~12.0 GiB of weights
  at 16k f16 KV, which reaches roughly IQ3_M and no further; IQ4_XS needs the desktop apps
  closed. This is the quant ladder to run next.
- **No mechanism.** Nothing here identifies the kernel or the code path. `AFM-17` applies —
  this is all runtime behaviour, no source claim.
- **Bug A did not reproduce here — for buun specifically.** `q8_0` symmetric at D=256 on
  sm_60 was **clean 10/10**, where `RESULT_OWNERSHIP.md` recorded collapse 3/3 on buun
  `a8e5b5a38`. This says nothing about TheTom `f6124e9`, which is where U_E's collapse was
  measured. Three differences:
  single GPU vs dual, buun `02f8581c65` vs `a8e5b5a38`, IQ2_M vs Q6_K. **Untested which** —
  it needs a 2-GPU arm before anyone concludes Bug A is fixed.
- **Fidelity is not measured.** "Clean" means not degenerate. No quality claim anywhere.
