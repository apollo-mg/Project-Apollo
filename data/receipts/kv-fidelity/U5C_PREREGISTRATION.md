# U5c pre-registration — decision rule fixed before the tier data existed

**Written 2026-08-18**, after the f16/f16 control returned an exact null at 128 prompts and
**before any 8-bit or 4-bit arm reported.** Committed ahead of the results so the analysis
rule cannot be chosen to fit them.

## The question

Mark: *"Turbo codecs, iirc, always perform badly when symmetric due to the rotation math."*
h4rm0n1c called symmetric turboquant "bunkum". Mechanism available in buun's own header:
turbo8 is *"no QJL"* with *"FWHT outlier suppression"* — **no random projection, so the
Walsh-Hadamard rotation is deterministic**, and a symmetric pair gives K and V an identical
transform whose errors can then correlate.

The confound is that every turbo type is also the *cheaper* side of its comparison, so a
naive "turbo lost" reading is unidentifiable against simple bit budget. U5c fixes budget.

## Arms (bits/value from source)

| tier | A (sym, non-turbo) | B (mixed) | C (mixed) | D (sym, turbo) |
|---|---|---|---|---|
| **8-bit** | `q8_0`/`q8_0` **17.00** | `q8_0`/turbo8 **16.625** | turbo8/`q8_0` **16.625** | turbo8/turbo8 **16.25** |
| **4-bit** | `q4_0`/`q4_0` **9.00** | `q4_0`/turbo4 **8.625** | turbo4/`q4_0` **8.625** | turbo4/turbo4 **8.25** |

B and C sit at the exact midpoint of A and D in bits. That is the whole design.

## Decision rule

Let `X = (R_B + R_C)/2` be the observed mixed mean.

**Primary null (geometric):** `M_geo = sqrt(R_A · R_D)`. Quantization error scales roughly
as `2^(−bits)`, and R spans 0.087→362 across this ladder, so a log-scaled interpolation is
the honest null. Linear `M_lin = (R_A + R_D)/2` is reported alongside but is **not** the
primary.

| observed | verdict |
|---|---|
| `X < R_A` | **strong** symmetry effect — mixed beats the best symmetric arm despite costing fewer bits than it |
| `R_A ≤ X < 0.9·M_geo` | **moderate** symmetry effect |
| `0.9·M_geo ≤ X ≤ 1.1·M_geo` | **bit-budget** — no symmetry effect detected |
| `X > 1.1·M_geo` | anti-symmetry / unmodelled; report as such |

Applied **independently per tier**. A result counts as supporting the symmetry hypothesis
only if it lands in *strong* or *moderate*.

**Pre-registered confidences:** P1 (8-bit tier shows a dip) **0.50**. P2 (4-bit tier shows a
dip) **0.60** — larger absolute errors leave more headroom to resolve. P3 (f16 control exact
null) **0.97** — **already CONFIRMED** at 128 prompts.

## Guards

- `R_B` and `R_C` are *both* measured rather than assumed symmetric under K/V swap. If they
  differ substantially, that is itself the K-vs-V asymmetry h4rm0n1c described (*"lose a
  value and a key might point to something near enough; lose the key and no value gets
  found"*) and must be reported separately from the symmetry question.
- Every arm keeps full stderr, so the `q8_0`-fallback warning
  (`llama-kv-cache.cpp:894-914`) would be visible if it fired. It must not.
- `KV buffer size` is captured per arm to check the source-derived bits arithmetic
  **empirically** — this project has a prior 3.8× KV-size overestimate from trusting
  arithmetic alone.
- `mean_L` is excluded from all verdicts: it is a mean of a ratio with a near-zero
  denominator and read −5.74 / +2.32 in U5b. `frac_L≥1` is the robust form.
- n=128 prompts. U5b's n=16 could not resolve the 8-bit pair (1 vs 6 events, p≈0.12); if
  the 8-bit tier is still event-starved at 128, **say so rather than reading the ranking.**
