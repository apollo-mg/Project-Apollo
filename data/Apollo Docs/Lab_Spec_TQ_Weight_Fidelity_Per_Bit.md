# Lab Spec — Is TurboQuant good *for weights*? A fidelity-per-bit ladder

**Status:** proposed, 2026-08-03. Feasibility gates verified (below).
**Motivation:** TQ's published wins are for **KV cache**. For **weights** there is, as far as we can
find, no published fidelity analysis at all — only throughput anecdotes and packagers' claims. The
question "does TQ buy fidelity per bit versus k-quants/i-quants" is open, answerable with tooling we
already have, and nobody has answered it.

## Feasibility gates — all verified on `TheTom/llama-cpp-turboquant` @ `d0e2a8b64`

| gate | result |
|---|---|
| Fork can quantize **to** TQ | ✅ `{"TQ3_1S", …, " 4.00 bpw WHT-rotated"}`, `{"TQ4_1S", …, " 5.00 bpw WHT-rotated"}` in `tools/quantize/quantize.cpp` |
| Their labels match measured reality | ✅ our tensor-offset probe independently measured 16.000 B/32 = 4.00 bpw and 20.000 B/32 = 5.00 bpw |
| `llama-perplexity` supports KLD | ✅ `kl_divergence` present |
| Apples-to-apples control | ✅ `--pure`, `--output-tensor-type`, `--token-embedding-type`, `--imatrix` all available |

## ⚠️ The finding that shapes the entire design: **TQ ignores the imatrix**

```c
size_t quantize_tq4_1s(const float * src, void * dst,
                       int64_t nrows, int64_t n_per_row, const float * imatrix) {
    GGML_UNUSED(imatrix);
    ...
    quantize_row_tq4_1s_ref(...)   // pure reference quantizer, no importance weighting
}
```
(`ggml/src/ggml-turbo-quant.c`; identical for `quantize_tq3_1s`.)

**TQ weight quantization is calibration-free.** It takes the parameter only to satisfy the
`ggml_quantize_chunk` interface and discards it. Every k-quant/i-quant it would be measured against
uses activation-derived importance weighting.

That forces **two distinct questions**, which must not be conflated:

- **Q-A (format):** is the WHT-rotation + Lloyd-Max idea better per bit than k-quant packing, holding
  calibration constant? → compare **without imatrix on both sides**.
- **Q-B (practical):** should someone download a TQ file instead of a `Q4_K_M` file? → compare
  TQ (which *cannot* use imatrix) against k-quants **with** imatrix, because that is what ships.

Q-A and Q-B can easily give opposite answers. If they do, that *is* the headline: TQ's rotation is
sound but it is leaving calibration on the table, and **TQ+imatrix is an unimplemented, concrete
improvement** worth proposing upstream.

## Phase 0 — Build validation (non-negotiable)

Tonight's session proved a build can silently produce garbage on TQ4_1S with `cuda_err=0` and
*identical throughput* (`TQ4_1S_PASCAL_REGRESSION.md`). **A fidelity number from an unvalidated
build is worthless.**

1. Build `d0e2a8b64` (known-good for TQ4_1S) with targets `llama-quantize`, `llama-perplexity`,
   `llama-imatrix` — *currently only `llama-server` is built*.
2. Gate: generate a short greedy completion from a TQ4_1S model on **CPU** and on **CUDA** and
   require agreement (or at minimum, coherence on both). Abort the study if they diverge.
3. Record build SHA, GPU clock/power state, and driver in every result file.

## Phase 1 — The matched ladder (core experiment)

**Why matched:** the public TQ files are *not* comparable to public k-quant files. Measured tonight,
same base model (Qwen3.6-27B + MTP, 866 tensors both):

| file | TQ tensors | other |
|---|---|---|
| MidnightPhreaker TQ4_1S | 180 @ 5.00 bpw | 258 × Q8_0, 60 × Q4_K |
| YTan2000 TQ3_4S | 480 @ 4.00 bpw | 17 × Q6_K, 8 × Q4_K |

Comparing those measures **packagers' coverage choices**, not formats. The only valid method is to
quantize everything ourselves from one base with `--pure`.

**Base model:** a small dense model with fp16/bf16 weights available — **4B–9B class**. Rationale:
smaller models are *more* sensitive to quantization damage (better signal), the whole ladder fits in
tens of GB, and every arm runs in minutes. 27B is Phase 3, not Phase 1.

**Arms** — one `fp16` base → all of:

| arm | nominal bpw | role |
|---|---|---|
| `fp16` (or `Q8_0`) | 16 / 8.5 | reference for KLD |
| **TQ3_1S** | **4.00** | TQ aggressive |
| **TQ4_1S** | **5.00** | TQ moderate |
| `IQ4_XS` | 4.25 | i-quant vs TQ3_1S |
| `Q4_K_S` | ~4.5 | |
| `Q4_K_M` | ~4.85 | k-quant vs TQ4_1S |
| `Q5_K_S` | ~5.5 | k-quant *above* TQ4_1S |

All produced with `--pure` and **no** imatrix. `--output-tensor-type` and `--token-embedding-type`
pinned identically across arms so only the body tensors vary.

**Measure actual bpw per arm with `tensor_bpb.py`** — never trust the filename, the label, or the
file size. Tonight produced three separate errors from exactly that mistake.

**Metrics**, primary → secondary:
1. **KL divergence vs the fp16 reference** — median, mean, p99. Primary. Far more sensitive than PPL
   and the established metric in this project (`pascal-kv-finding` used median KLD + same-top%).
2. **same-top-1 %** — the "does it pick the same token" measure.
3. **PPL** on a standard set — secondary, for comparability with published numbers.

**The plot that answers the question:** median KLD (y, log) vs **measured** bpw (x). TQ is a win iff
its points sit below the k-quant/i-quant curve at equal bits.

**Pre-register before running.** Suggested: TQ4_1S@5.00 beats Q4_K_M@4.85 on KLD (it has ~3% more
bits) but *loses* to Q5_K_S@5.5; TQ3_1S@4.00 loses to IQ4_XS@4.25 because i-quants at that size lean
hardest on calibration, which TQ has none of.

## Phase 2 — The calibration axis

Re-run the k-quant/i-quant arms **with** an imatrix (single shared calibration corpus; record it).

This isolates how much of any k-quant advantage is calibration rather than packing, and answers Q-B.
Deliverable: a single number — "imatrix is worth *N* bpw-equivalent at this size" — which is
independently useful and, again, not something we have seen published.

## Phase 3 — Scale check

Repeat only the 2–3 most informative points on Qwen3.6-27B (we already hold TQ4_1S and Q6_K files,
plus a `bandtor` 35B-A3B MoE) to confirm the curve's *shape* survives scale. Fidelity conclusions
from a 4B do not automatically transfer.

## Phase 4 — Speed and VRAM (report separately)

**Fidelity is hardware-independent; speed is not.** Keep these axes apart or the story gets muddled.
Already measured on 2×P100 (sm_60), `TQ4_1S_PASCAL_REGRESSION.md`:

- native TQ4_1S (5.0 bpw) is **5.8% slower** than converting it to q8_0 (8.5 bpw) — `__dp4a` is
  sm_61+, P100 is sm_60, so the WHT/centroid kernel goes scalar and ALU-bound
- but native TQ4_1S still beats Q6_K by **+16%** at 24% fewer bits
- default path silently converts TQ4_1S→q8_0, so **any TQ speed number taken with default flags is a
  q8_0 number** — `GGML_TQ_NATIVE=1` is mandatory for TQ speed measurement

**Missing and high value: RDNA4 (RX 9070 XT) and Turing (1660 Ti).** Both have a native INT8 dot
(`__builtin_amdgcn_sudot4` / `__dp4a`) that P100 emulates in ~7 scalar ops. If TQ's math is "free"
on hardware with the instruction, that is where it shows. Mark is turboquant's only AMD hardware,
so the 9070 XT number is unobtainable elsewhere.

## Out of scope / stretch

- **turbo-tan `TQ3_4S`** (4.00 bpw, id 46 — collides with TheTom's TQ4_1S) is a *different fork's*
  format and cannot be produced by TheTom's `llama-quantize`. Including it requires building
  `turbo-tan/llama.cpp-tq3` (remote already configured, no checkout). Worth one arm if Phase 1 shows
  TQ is competitive, since the TQ3_4S corpus on HF is larger than the TQ4_1S one.
- MLX TurboQuant implementations — different codebase, not comparable.

## Resources

| | |
|---|---|
| disk | 4B ladder ≈ 8 arms × ~2.5 GB + fp16 ≈ 28 GB. `.73` has ~31 GB free *after* the bandtor download; `.194` has 109 GB but is running BFCL. Prefer `.194` once free. |
| compute | quantize: minutes/arm. KLD: one reference-logits pass + one pass per arm. |
| blockers | build `llama-quantize`/`llama-perplexity`/`llama-imatrix` (Phase 0); pick + fetch an fp16 base |

## Why this is publishable

- No article exists on **TQ for weights** — only KV-cache results and vendor claims.
- The imatrix finding (`GGML_UNUSED(imatrix)`) is a concrete, verifiable, previously-unstated fact
  with a direct implication for whether TQ can compete at low bpw.
- The method (matched `--pure` ladder + KLD vs measured bpw) is reusable for *any* new quant format,
  and the tooling (`tensor_bpb.py`, `hf_tq_probe.py`) already exists from this session.
- Natural companion piece to the interop findings: `TQ_ENUM_DRIFT_INTEROP.md`,
  `HF_TQ_CORPUS_AUDIT.md`, `TQ4_1S_PASCAL_REGRESSION.md`.
