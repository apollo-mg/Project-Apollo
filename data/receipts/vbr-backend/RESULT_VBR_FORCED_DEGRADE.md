# VBR walks the ladder cleanly on Qwen3.8-27B at 2/3 bpw — 30/30 under an 8x budget squeeze

**2026-09-03.** RX 9070 XT (gfx1201), buun-llama-cpp `3823c9eb6` (contains `424c3361e`).
Corrected re-run of `RESULT_VBR_QWEN38_GSQ.md`, whose budgets were too generous to force
degradation. Raw: `raw_vbr_forced.jsonl` / `.log`, per-arm server logs alongside.

## Design fix

The 2,133-token probe needs **~133 MiB of KV at f16** (16 KV layers x 64 KiB/token — the
model is a hybrid, see `../gguf-librarian/RESULT_DIRK_GSQ_RCO_HYBRID.md`). Every budget here
is *below* that, so the controller must degrade or fail. Confirmed by the controller itself,
on all five VBR arms:

```
W VBR dynamic: the KV budget (16 MiB) is below the full-context cost at the
  1.25 bits/value floor (~160 MiB) — the deepest fills will hit the floor clamp early
```

Degradation confirmed by output divergence, not by a log line: **3 of 6 cells per arm are
byte-identical to the f16 control, 3 of 6 differ.** The identical three are the short
`schema_copy` probe (113 tokens — too small to reach any budget); the differing three are the
long probe. Exactly the expected split.

## Result: 30 of 30 clean

| arm | budget | squeeze vs f16 working set | schema copy | long prose |
|---|---|---|---|---|
| `iq3_f16` | — | 1x (control) | 3/3, ctok 277 | 3/3, ctok 495 |
| `iq3_vbr_96` | 96 MiB | 1.4x | 3/3, ctok 277 | 3/3, ctok 510 |
| `iq3_vbr_64` | 64 MiB | 2.1x | 3/3, ctok 277 | 3/3, ctok 494/516/516 |
| `iq3_vbr_32` | 32 MiB | 4.2x | 3/3, ctok 277 | 3/3, ctok 634/602/602 |
| `iq3_vbr_16` | 16 MiB | **8.3x** | 3/3, ctok 277 | 3/3, ctok 458 |
| `iq2_vbr_64` | 64 MiB | 2.1x | 3/3, ctok 122 | 3/3, ctok 454 |

**The headline number.** The three fixed terms — including `intimate_proximity_threshold`,
chosen because `turboquant#311` reports it corrupting to `intimate_proximiti` — come back
**character-exact in 18 of 18 schema-copy cells**, across every budget down to 16 MiB and on
both quants. An 8x KV squeeze does not touch verbatim copy fidelity on this model.

Long-prose output varies with budget, as it must — different cache precision, different
trajectory at temp 0 — but every one of the 15 VBR long-prose cells is coherent, on-topic
and >200 characters. No empty content, no runaway, no structure-soup.

## Prediction scoring vs `PREDICTION_VBR_QWEN38_GSQ.md`

| # | prediction | conf | outcome |
|---|---|---|---|
| P3 | a forced small budget actually degrades | 0.75 | **HIT** on the corrected budgets (it was FALSIFIED at 256 MiB) |
| P4 | output stays coherent under forced degradation | 0.70 | **HIT — 30/30** |
| P5 | IQ2_XS degrades quality more than IQ3_XXS at equal budget | 0.55 | **NOT SUPPORTED** — both 3/3 at 64 MiB; this probe set cannot resolve a quality *gradient*, only collapse |
| P1 / P6 | degrade order resolves via KV-layout fallback / MTP breaks the set match | 0.65 / 0.30 | **STILL UNRESOLVED** — see below |

## The prior run's anomaly did not recur

`RESULT_VBR_QWEN38_GSQ.md` recorded one cell (`vbr_auto`, long prose, rep 3) returning
`finish=length`, 1,200 tokens, zero content — the pre-fix collapse signature. **It did not
reproduce in any of these 30 cells**, including at budgets 300x tighter. That leaves it a
single unreproduced observation on the auto-budget arm. Still not worth reporting; now also
not worth chasing until it appears twice.

## Open question worth handing to buun

**No `VBR degrade order:` line is emitted on any arm, at any budget, even when degradation
demonstrably occurred.** The baked table is consumed by the dynamic path
(`llama-kv-cache.cpp:80`, `vbr_degrade_order_[order_ordinal]`), so an order *is* resolved —
it just never announces which one.

That matters for this model specifically: `vbr_baked_orders` keys on `(arch, n_layer_all)`
and holds `{LLM_ARCH_QWEN35, 64, vbr_order_q27}`, while Qwen3.8-27B is `n_layer_all = 65`
(the MTP layer). There is a second-pass fallback matching the exact KV-layer-id set, and
whether it hits depends on whether blk.64 takes a cache slot — 16 KV layers matches the
table, 17 does not and falls through to a generic order.

From outside the process there is no way to tell which happened. A one-line log at
selection time would make it observable. **Everything above is correct regardless** — the
output is clean either way — but "which ladder is this model actually using" is currently
unanswerable from the logs.

## Caveats

- K=3. Clean at 30/30 with zero failures, so no rate to estimate, but this is not a
  long-horizon soak.
- Longest prompt is 2,133 tokens. Deep-context behaviour (16k+) is untested, and the
  controller's own warning says "the deepest fills will hit the floor clamp early".
- Explicit `-ctk vbr -ctv vbr` sets the floor to **1.25 bits/value**, the bottom of the
  ladder. Implicit VBR uses a 4.125 floor. These arms are therefore more aggressive than a
  default user's configuration, which makes 30/30 a stronger result than it first appears.
