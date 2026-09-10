# VBR at ~4.2 bits/value retrieves 18/18 — including at 147,772 tokens, where f16 cannot run

**2026-09-03.** RX 9070 XT 16 GiB (gfx1201), buun-llama-cpp `3823c9eb6`,
`Qwen3.8-27B-GSQ-RCO-IQ3_XXS-mtp` (ISTA-DASLab GSQ-RCO, 3.05 bpw).
Pre-registered in `PREDICTION_VBR_DEEP_RETRIEVAL.md`. Raw: `raw_deep_retrieval.jsonl` / `.log`.

Tests Mark's claim: *"if the pricing ladder is doing real work — and I think it is — 4.3 avg
bpv is more than enough if it's allocated intelligently."*

## Result

Needle-in-haystack, three distinctive facts at ~10% / ~50% / ~90% of the fill, temp 0,
seed 42, K=2. Scored on exact retrieval of the value string.

| arm | KV | effective bpv | context | prompt tokens | VRAM | 10% | 50% | 90% |
|---|---|---:|---:|---:|---:|:-:|:-:|:-:|
| A | f16 | 16.000 | 65,536 | 42,241 | **97%** | 2/2 | 2/2 | 2/2 |
| B | vbr, floor t4 | **4.217** | 65,536 | 42,241 | **72%** | 2/2 | 2/2 | 2/2 |
| C | vbr, floor t4 | **4.217** | 262,144 | **147,772** | **73%** | 2/2 | 2/2 | 2/2 |

**18 of 18.** Every answer exact — `47.3 kelvin-seconds`, `812 milliamperes`,
`1,596 microseconds` — and A and B are byte-identical to each other at matched depth.

## What the numbers mean

- **A 3.8x cut in KV bitrate cost nothing measurable.** 16.0 -> 4.217 bits/value, same
  content, same answers, 25 percentage points of VRAM handed back (97% -> 72%).
- **Arm C is not an optimisation, it is a capability.** f16 tops out at **71,177 tokens** in
  this budget (4.34 GiB / 64 KiB per token). Arm C answered at **147,772 tokens — 2.08x the
  f16 ceiling** — at 73% VRAM, with room to spare. There is no f16 control for that row
  because f16 cannot reach it on this card.
- The controller's own accounting: `floor mix costs 1.382e+05 bits/token vs 1.352e+05 at the
  pricing tier`, auto budget **5,248 MiB**. 138,200 bits/token over 32,768 values = **4.217
  bits/value**.
- **No lost-in-the-middle effect at any bitrate.** The 50% needle scored identically to the
  10% and 90% needles in all three arms.

## Prediction scoring

| # | prediction | conf | outcome |
|---|---|---|---|
| P1 | A retrieves 3/3 at all depths | 0.80 | **HIT** |
| P2 | B matches A within one needle | 0.65 | **HIT** — matched exactly, not within one |
| P3 | B degrades most at the middle depth | 0.45 | **VACUOUS** — nothing degraded anywhere |
| P4 | C retrieves the 90% (most recent) needle | 0.70 | **HIT** |
| P5 | C retrieves the 10% (oldest) needle | **0.35** | **HIT — my pessimism was wrong** |
| P6 | no collapse signature in any arm | 0.85 | **HIT** — every cell `finish=stop` |

**P5 is the one worth keeping.** I put 0.35 on the oldest needle surviving a 148k
floor-clamped cache and it came back 2/2, exact. The controller's own warning
(*"the deepest fills will hit the floor clamp early"*) describes an allocation behaviour, not
a retrieval failure — and I read it as the latter.

**Mark's claim is supported.** At ~4.2 bits/value the ladder gave up nothing this probe can
detect, at 3.5x the context f16 could hold.

## Scope — what this does NOT show

- **Retrieval is not reasoning.** An exact-string needle is the easiest long-context task
  there is. This says nothing about multi-hop synthesis over 148k tokens, where a lossy cache
  has far more room to hurt.
- K=2, three needles, one haystack, one model, one quant. 18 cells is an existence proof.
- Filler is homogeneous technical prose. A haystack of near-duplicate distractors would be a
  much harder test of a quantized cache.
- 147,772 tokens, not the full 262,144 the slot allocates. The top 44% of native context is
  still unexercised.
- Nothing here measures *speed* at depth; prefill at 148k took minutes per request.

## Three harness bugs, all mine, before a single valid row appeared

1. **A 221 KB JSON body passed to `curl -d "$body"`** as a shell argument. Silently produced
   no response and no row — the log showed empty `got=""` fields with no error anywhere.
   Fixed by staging the body on disk and using `--data-binary @file`.
2. **`max_tokens: 120` consumed entirely by the thinking block**, so the f16 control returned
   `finish=length` with empty content. **This is the second time today** I under-budgeted
   tokens against this model's reasoning and nearly recorded a null result as a finding — the
   first was `RESULT_TURBO_COLLAPSE_NONREPRO.md`. Raised to 400.
3. **Port-busy abort** when a restart raced the previous teardown. This one is the guard
   working: it refused to run rather than answering from a foreign service, which is exactly
   the failure that served six probes off `apollo-wake-proxy` earlier today.

Teardown verified clean: 0 servers, 12% VRAM.
