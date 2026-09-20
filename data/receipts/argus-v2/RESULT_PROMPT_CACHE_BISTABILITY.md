# Result -- prompt-cache reuse makes generation bistable; it is the determinism blocker

**2026-09-20, `.73`** (2x Tesla P100, sm_60), buun `08826ad6`, `Qwen3.8-27B-Q6_K`, `-sm tensor`,
`-ctk vbr -ctv vbr --vbr-floor t2`, `-np 1`, `--spec-type draft-mtp --draft-max 3`.

Card sampling throughout: `temp 1.0 / top_p 0.95 / top_k 20`, **fixed seed 12345**, identical
prompt every request.

## The finding

| prompt cache | `cached_tokens` | distinct outputs | n |
|---|---:|---:|---:|
| on, cold prefix | 0 | **1** | 6 |
| **on, warm prefix** | **30 of 34** | **2, strictly alternating** | 14 |
| `cache_prompt: false` | 0 | **1** | 6 |

With 30 of 34 prompt tokens served from cache, output alternates with **period 2** -- odd requests
one continuation (1354 chars, `finish_reason: length`), even requests another (1312 chars,
`stop`), 7 and 7, no exceptions across 14 consecutive requests. Turn the cache off and six of six
are byte-identical.

**This is causal, not correlational**: the only variable changed in the last arm was
`cache_prompt: false` on the same live server, same seed, same prompt.

The stable output under every cold-cache condition is `eda9903162a01d4f` -- **the same hash the
previous binary (`c9c52d71`) produced 24 times running**. So the cache is not producing a
"wrong" answer so much as a *second* answer.

## Why the earlier determinism gate missed it, and said so

`RESULT_TENSOR_SPLIT_DETERMINISM.md` recorded, as one of four stated gaps:

> **Prefix caching, specifically.** `cached_tokens` was 0 throughout, so the cache path was
> **never exercised**. A real agentic run hits it constantly. Determinism under cache reuse is
> untested and is the likeliest place for this result not to hold.

It did not hold. The gate's pass was real for what it measured and useless for what the campaign
needs, which is exactly what the gap said.

## Likely mechanism, not yet proven

`llama-server --help` on this build carries `--vbr-prompt-cache`: *"publish idle dynamic-VBR slots
as projected prompt-cache artifacts"*. Under variable-bitrate KV, a **cached** prefix is stored at
whatever precision its slot held, while a **freshly computed** prefix is produced at the current
precision -- different bit-depth, different logits, different continuation. The `/slots` endpoint
also exposes a buun-specific `computation_frontier_ratchet` carrying `flips_total` and
`fallbacks_total` counters, which is suggestive but was not instrumented here.

**Untested:** whether f16 KV shows the same bistability. If VBR is the mechanism, f16 should be
clean, and that is a cheap discriminator worth running before blaming the cache generally.

**Also untested: whether this is a REGRESSION.** The old binary was never observed with a cache
hit (`cached_tokens` 0 on all 25 requests), so it may share the behaviour. Do not report this
upstream as "new in `08826ad6`" without running the old build with a warm prefix.

## What it costs the campaign

Corpus v2 relies on **paired seeds** -- the same seed set across arms, so comparisons are paired
rather than independent. Multi-turn agentic runs hit the prefix cache on essentially every turn
after the first. Under cache reuse the same seed does not reproduce, so **pairing would be
fiction**: arm A's odd-numbered turns would be compared against arm B's even-numbered turns and
the difference read as a codec effect.

**Mitigation: `cache_prompt: false` on every campaign request.** It restores determinism at the
cost of re-prefilling the full context each turn.

**And that collides with `preserve_thinking`.** The v2 spec pins `preserve_thinking` at its
shipped default (ON) and justifies the context growth on the grounds that the prompt stays
*append-only and therefore cacheable*. Disabling the cache removes precisely that compensation:
the context still grows with every preserved reasoning block, and now every turn re-prefills all
of it. **The cost is quadratic in turn count** -- turn N re-prefills the sum of all prior
reasoning.

Three options, none free:

1. **Cache off, accept the prefill cost.** Deterministic, paired seeds real, campaign slower --
   and the slowdown compounds with `preserve_thinking`.
2. **Cache on, abandon paired seeds**, raise K and treat runs as independent. Loses statistical
   power exactly where the design was buying it.
3. **Cache on with `preserve_thinking: false`.** Smaller contexts, but the prompt is rewritten
   each turn so the cache mostly misses anyway, and it deviates from the shipped default.

**Recommendation: option 1**, with the prefill cost measured in the pilot rather than estimated.
The pilot now has a third job beyond rung separation and token consumption: **quantify what
`cache_prompt: false` costs per turn under `preserve_thinking`.**

## Connects to a previously unexplained result

`[[agent-benchmark-determinism]]` records bistable agent results that were never explained, and
`[[server-uptime-is-a-variable]]` names uptime as the leading hypothesis for them. **Prompt-cache
reuse is a better candidate**: it is reproducible on demand, it produces exactly two states rather
than drift, and it requires no elapsed time at all -- the second request already shows it.

Not claimed as settled for those older runs, which were never instrumented for `cached_tokens`.
Stated so the hypothesis can be tested rather than inherited.

## Credit

The cache hypothesis was Mark's, offered in one word while the alternation was still being
characterised, and it was correct.
