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

## Reproduction, and the trigger

**Reproduced exactly after a server restart**: same two hashes (`ff82d31f...` odd / `802ada7a...`
even), same lengths, same finish reasons, `cached=0` on request 1 then `cached=30` from request 2
onward. 10 for 10, no exceptions.

**The trigger is a FRESH SERVER.** Between the first observation and the reproduction there was a
window where the same prompt returned `cached_tokens: 0` and stable output, with the slot
reporting `cache_status: "full reprocess: no reusable context checkpoint"` -- the cache simply
stopped engaging. The difference: that window followed a run of `cache_prompt: false` requests.

**So `cache_prompt: false` appears to suppress caching in the slot PERSISTENTLY, not just for the
request carrying it.** Observed, mechanism unverified. Convenient for the mitigation, but do not
rely on the side effect -- send the flag on every request that must reproduce, because a behaviour
nobody documented is not a guarantee.

This also means **any determinism result is invalid unless `cached_tokens` is recorded with it.**
A run that happens to land in the non-caching window looks perfectly deterministic and proves
nothing about the warm path.

## Ruled out: the frontier ratchet

The `/slots` endpoint exposes a buun-specific `computation_frontier_ratchet` carrying
`agreement_streak`, `agreements_total`, `disagreements_total`, `flips_total` and `fallbacks_total`
-- a plausible shape for a two-path A/B mechanism producing period-2 output. **It is not the
cause.** Every counter read zero both before and after a batch of warm-cache requests, and
`read_path` stayed `legacy` throughout. The ratchet is inert on this build.

## Ruled out: VBR precision adaptation

An f16-KV arm was run to test whether variable bit-depth explained it: same binary, same flags,
`-ctk f16 -ctv f16`, context reduced to 8192 (f16 KV will not fit 262144 in 32 GB). Result:
**bistable, with the IDENTICAL two hashes** (`ff82d31f...` / `802ada7a...`), 8 of 9 valid
requests at `cached_tokens: 30`.

**As a VBR-vs-f16 discriminator that arm is VOID, and the identical hashes are the proof.**
`/slots` reports `kv_bpv: 16.0` under BOTH configurations, because `--vbr-entry` defaults to f16
("quality-first default") and degrades toward `--vbr-floor` only under pressure -- which a
34-token prompt with ample VRAM never creates. The two arms were the same arithmetic with
different labels, so of course they agree.

**But it still rules the hypothesis out, by a different route.** Precision never varied between
the cached and the fresh path -- both f16, `kv_bpv` constant at 16.0 before and after -- and the
bistability occurred anyway. **A mechanism that requires a precision difference cannot explain an
effect observed where there is none.**

So the divergence is *structural in the cache-reuse path*, not numerical: reusing a checkpoint
computes something measurably different from recomputing the same prefix at the same precision.

**Still untested:** whether genuinely low-precision VBR (`--vbr-entry turbo3`, or enough VRAM
pressure to force degradation toward the `t2` floor) introduces a *separate* effect on top. That
is a different question from the one this arm was meant to answer.

## ISOLATED: speculative decoding is required for the bug

Four arms, same binary flags otherwise, same prompt, same seed, fresh server each time:

| arm | warm requests | distinct outputs | verdict |
|---|---:|---:|---|
| new `08826ad6`, MTP on, VBR | 9 | **2, alternating** | bistable |
| new `08826ad6`, MTP on, f16 | 8 | **2, alternating** (same hashes) | bistable |
| **new `08826ad6`, MTP OFF** | **8** | **1** | **CLEAN** |
| old `c9c52d71`, MTP on, VBR | **0** | 1 | VOID -- cache never engaged |

**With `--spec-type draft-mtp --draft-max 3` removed, 9 of 9 requests are byte-identical,
8 of them at `cached_tokens: 30`.** The warm-cache path is deterministic on its own. It is the
combination of cache reuse AND speculative decoding that diverges.

**The first-request anomaly is the same bug.** Without MTP even request 1 (cold, `cached=0`)
matches the rest. The "discard a warmup generation" rule derived earlier today was treating a
symptom -- the cause is MTP state, not kernel autotune or lazy allocation as guessed there.

### Not split-mode specific -- and `-sm layer` is WORSE

| split mode | warm reqs | distinct outputs | pattern |
|---|---:|---:|---|
| `-sm tensor` | 9 | **2** | clean period-2, odd/even |
| `-sm layer` | 8 | **6** | even requests consistent (`109df7fb` x4), **odd requests all different** |

`-sm layer`, MTP on, everything else identical:

```
[1] 6eb36d5b len=1297 cached=0     [2] 109df7fb len=1190 cached=30
[3] 5602b694 len=1387 cached=30    [4] 109df7fb len=1190 cached=30
[5] 5a93cd32 len=1387 cached=30    [6] 109df7fb len=1190 cached=30
[7] 6cc37ea6 len=1281 cached=30    [8] 109df7fb len=1190 cached=30
[9] a78a05e1 len=1361 cached=30
```

So the defect is **not** tensor-parallel specific. Under layer split it degrades from a clean
two-state alternation into one stable state on even requests and an unstable one on odd requests
-- five distinct outputs across five odd requests.

**The odd/even structure is suggestive, not established**: n=9, and a run of that length cannot
distinguish "odd requests are unstable" from "most requests are unstable and the even ones
coincided". The headline -- layer split is affected and produces MORE distinct outputs than
tensor split -- is solid either way.

No layer-specific warnings appeared in the server log.

## Why it appears only now: the old build never reached this path

The old binary reported `cached_tokens: 0` on every request, and its log says why:

```
W load_model: automatic dynamic VBR host caching fallback=live_only
   reason=artifact_topology_unavailable store_status=unavailable; cache-ram disabled
E slot: MTP checkpoint companion skipped: target=... draft=... spec=... state-ready=1
```

Host caching fell back to `live_only` and MTP checkpointing was skipped outright. The new build
emits neither line. **So this is not a regression in the ordinary sense -- it is a newly reachable
path.** Mark's read on first seeing it was exactly this: something that was not working now works,
and the newly working thing has a defect.

**Bisect pointers, by commit message rather than by bisecting:**

- **`30da59942` "server: retire static cache planner and lift host-prefix cutoff"** (2026-09-18) --
  *"Allow short positive host-prefix matches without a source-coverage cutoff."* The repro prompt
  is 34 tokens; a short-prefix cutoff is precisely what would have suppressed caching before.
- **`c7f114d34` "server: reuse active historical prefixes with checked MTP state"** -- names both
  halves of the interaction.
- Also in range: `5dfae0841` (prefix reuse with dynamic VBR), `3d94af142` (recycled VBR SWA
  prefixes), `07b89e4f7` (legacy checkpoint spacing).

Not bisected. Offered as candidates, not as a diagnosis.

## Likely mechanism, not yet proven

**Superseded in part by the f16 arm above** -- the precision story below is ruled out for this
observation, and is retained only because `--vbr-prompt-cache` remains a plausible route for
*low-tier* VBR, which was never reached here.

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
