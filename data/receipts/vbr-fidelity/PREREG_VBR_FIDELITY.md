# Pre-registration — VBR fidelity, matched on achieved bitrate

**2026-08-25, written before any arm ran.** This is the arm that decides whether the article
can say "more context" or "more context **for free**." Those are different claims and only one
of them is currently supported.

## Conflict of interest, stated up front

Mark collaborates with the codec's author. That makes favourable-looking results *less*
credible unless the method is fixed in advance and the disconfirming outcomes are named before
they can be rationalised. Everything below is registered before data exists.

## What is already established (mechanism, not quality)

From `../vbr-dynamic/` and this week's probes, all reproducible:

- dynamic VBR **engages**: `entry tier f16, floor N bits/value, price-ordered decode-time degrades`
- it degrades **smoothly** under pressure: 15.51 → 11.82 → 7.88 → 6.11 bpv observed
- **the floor binds literally**: floor 6 stops at 6.109; floor 2.25 continues to 3.844
- **zero evictions** across a full fill — it degrades instead of dropping cache
- throughput is barely affected: 1.16 → 0.84 t/s across a 12× context increase

**None of that is a quality claim.** Every "clean" verdict this project holds means *not
degenerate*, never *faithful*.

## The category error to avoid

`BACKLOG S4`: *"VBR has no fixed operating point; point comparisons against static codecs are
category errors, and one already produced a wrong conclusion."* Comparing VBR-at-whatever-it-
settles-on against static turbo3 measures two different bitrates and calls it a codec
difference.

**So every comparison here is matched on ACHIEVED bitrate**, read from `/slots kv_bpv` at the
moment of measurement — not on the flag that was passed.

## Arms

Target `Qwen3.8-27B-UD-IQ4_XS`, `.194` GPUs 0,1, 1063 MHz / 150 W, `-sm tensor -fit off`,
card sampling (`temp 1.0 / top_p 0.95 / top_k 20`), 3 seeds.

| id | KV config | achieved bpv | purpose |
|---|---|---|---|
| `F16` | `-ctk f16 -ctv f16` | 16.0 | reference ceiling |
| `S325` | `-ctk turbo3_tcq -ctv turbo3_tcq` | 3.25 static | the static codec at a fixed point |
| `V325` | `-ct vbr --vbr-floor 3.25`, filled until `kv_bpv` ≈ 3.25 | ~3.25 | **the matched comparison** |
| `V6` | `-ct vbr --vbr-floor 6`, filled until `kv_bpv` ≈ 6.1 | ~6.1 | buun's harness recommendation |
| `Q40` | `-ctk q4_0 -ctv q4_0` | 4.5 | what a stock-llama.cpp user would actually run |

`Q40` matters for the article: it is the honest alternative, not a strawman — and it is the
codec `RESULT_OWNERSHIP.md` measured **silently collapsing** at D=256 on both forks, which is
itself a finding a reader needs.

## Measures

1. **`tier_cal`** (16 items, 3 seeds) — the only instrument we own that can see calibration
   damage. `AFM-21`: teacher-forced fidelity metrics are structurally blind to it.
2. **Free-generation liveness** — `!`-fraction and a known-answer canary before and after a
   long generation, at depth.
3. **Throughput** at matched depth.

Deliberately **not** PPL or top-1 agreement alone: both are teacher-forced and both would have
missed every generation-level failure we found this month.

## Predictions

| # | prediction | conf |
|---|---|---|
| G1 | `F16` and `V6` are indistinguishable on `tier_cal` (≤1 item difference) | 0.75 |
| G2 | `V325` beats `S325` on `tier_cal` at matched bitrate | **0.50** |
| G3 | `Q40` shows measurable degradation vs `F16` | 0.60 |
| G4 | No arm produces `!`-collapse on sm_60 (routing fix present) | 0.85 |
| G5 | Throughput differs <10 % across all KV arms at matched depth | 0.70 |

**G2 at 0.50 is the honest number and the one that matters.** It is the entire premise of a
variable-rate codec over a static one at the same bitrate. If VBR does not beat static-3.25,
the adaptive machinery buys capacity and scheduling convenience, **not quality** — and the
article must say exactly that.

## Disconfirming outcomes, named in advance

- **G2 fails** → "VBR ≠ better quality at the same bitrate." Report it plainly; it does not
  invalidate the capacity or set-and-forget arguments, which stand on their own.
- **G1 fails** (floor 6 is visibly worse than f16) → buun's harness recommendation needs a
  caveat, and we tell him before publishing.
- **16 items is a gate, not a measurement.** No rate may be differenced from `tier_cal` at this
  size — `A1` is unbuilt. Any "X is better" claim needs the effect to be large enough that 16
  items can see it, or it does not go in the article.
