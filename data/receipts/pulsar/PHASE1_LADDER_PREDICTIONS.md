# Pre-registered predictions — TQ vs k-quants/i-quants, matched `--pure` ladder

**Logged 2026-08-04 BEFORE any quantization runs.** Phase 1 of
`Lab_Spec_TQ_Weight_Fidelity_Per_Bit.md`.

- Base: `unsloth/Qwen3.5-4B-GGUF` → `Qwen3.5-4B-BF16.gguf` (7.85 GiB), `qwen35` dense
- Build: `d0e2a8b64`, Phase-0 validated (`test-backend-ops` MUL_MAT 1344/1344, 3/3 backends,
  278 TQ cases, 0 FAIL, 0 NaN)
- All arms: `llama-quantize --pure`, **no imatrix on any arm**
- Arms: TQ3_1S, TQ4_1S, IQ4_XS, Q4_K_S, Q4_K_M, Q5_K_S
- Metric: median / mean / p99 KLD vs the BF16 reference, plus same-top-1 %

## Why no imatrix anywhere

TQ **cannot** use one — `quantize_tq4_1s()` begins `GGML_UNUSED(imatrix);`. Holding calibration
constant at zero is the only way to compare the *formats*. This is deliberately **TQ's best case**:
its whole premise (WHT rotation → near-Gaussian → Lloyd-Max optimal levels) is a purely
distributional argument that needs no calibration, while k-/i-quants are designed expecting one.
Phase 2 adds the imatrix axis and answers the different, practical question.

⚠️ `--pure` means these are **not** the files people ship. Shipped `Q4_K_M` keeps `output.weight` at
Q6_K and uses mixtures; shipped TQ files mix in Q8_0/Q4_K. Phase 1 measures formats, not products.

## Predictions

**P-F1 (0.6): TQ4_1S (5.00 bpw) beats `--pure` Q4_K_M (~4.85 bpw) on median KLD.**
It carries ~3% more bits, and rotation+Lloyd-Max is a principled fit for near-Gaussian weights —
the same family of idea as QuIP#/QuaRot incoherence processing. Uncalibrated k-quants are the
weakest version of their family, so this is where TQ should look good. Modest confidence because a
3% bit edge is small and Q4_K's 32-element sub-blocks with 6-bit scales give fine-grained local
adaptation that a fixed centroid table does not.

**P-F2 (0.55): TQ3_1S (4.00 bpw) loses to IQ4_XS (4.25 bpw).**
IQ4_XS has 6% more bits and a non-uniform codebook that remains effective without an imatrix. At
4 bpw, quantization damage rises steeply and small bit advantages matter more. Barely above a coin
flip — if TQ's rotation really does what it claims, 4.00 bpw beating 4.25 bpw is exactly the kind of
win it should be able to post.

**P-F3 (0.7): TQ4_1S (5.00) loses to Q5_K_S (~5.5).** A 10% bit advantage usually settles it;
I'd expect no format edge large enough to overcome that.

**P-F4 (0.85): measured bpw will exceed the nominal label on every arm**, because F32 norm tensors
and any non-quantizable tensors survive `--pure`. Magnitude small (norms are tiny). Recorded because
tonight produced **three** separate errors from trusting labels/filenames/file-size instead of
measuring — the x-axis of the final plot must be measured bpw.

**P-F5 (0.75): all six arms quantize without error.** `quantize_tq4_1s` asserts
`n_per_row % QK_TQ4_1S == 0` (32); Qwen3.5-4B's dims are multiples of 128. Residual risk is an
oddly-shaped tensor under `--pure` where a mixture would normally have rescued it.

## Calibration note

**My mechanism-based predictions went 0-for-4 tonight** (P-TS1, P-MTP2, P-TQ4, P-TQ5 — all
falsified), and in each case the error was reasoning from a plausible mechanism without first
checking which code path actually executes or what the right denominator was. Confidences above are
deliberately lower than my instinct, and P-F1/P-F2 are near coin flips because I have no prior at
all on TQ *fidelity* — only on its speed, which turned out to be governed by something (dp4a
availability) I had not considered.

## Scoring rules (fixed now)

- KLD computed with `llama-perplexity --kl-divergence` against BF16 logits from the same build.
- Identical corpus, context length, and seed across arms; recorded in the results receipt.
- Report median **and** p99: mean KLD is dominated by rare tokens and hides tail damage.
- Any arm that fails to quantize is a **result**, not a missing datum.
- Plot median KLD (log y) vs **measured** bpw. TQ wins iff its points sit below the k-/i-quant curve
  at equal bits.
