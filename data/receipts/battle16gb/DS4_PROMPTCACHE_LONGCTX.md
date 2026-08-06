# Prompt caching makes DS4-Flash usable on 4×P100: 8k-token turns go from ~9 minutes to ~30 seconds

`.194`, 4× Tesla P100-PCIE-16GB (sm_60, 1063 MHz / 150 W), 2× Xeon E5-2650 v3, 60 GiB
DDR4-2133. DS4-Flash UD-IQ1_S 82.5 GB, build `42974d12` (`version: 10245`, tree clean),
`-c 8192 -ngl 99 -sm layer -ts 3,4,4,1 -fit off -fa on -ncmoe 40`. Date 2026-08-01/02.
Supersedes the underpowered `DS4_PROMPTCACHE_INCONCLUSIVE.md` (~460-token context; this one
runs at ~8,000).

**Design:** a 36,658-char synthetic cluster document (7,976 tokens as tokenised) in turn 1,
then two short follow-ups. `max_tokens` 96 so **prefill dominates the measurement** instead of
decode. Fresh server process per arm.

## Result

| arm | turn 1 (doc) | turn 2 | turn 3 |
|---|---|---|---|
| `cache_prompt=false` | 7,976 tok / 658.2 s | **7,999 tok / 529.8 s** | **8,020 tok / 513.0 s** |
| `cache_prompt=true` | 7,976 tok / 579.7 s | **27 tok / 32.4 s** | **22 tok / 28.3 s** |
| **ratio** | 1.14× | **296× fewer tokens, 16.3× faster** | **365× fewer tokens, 18.1× faster** |

Uncached, every turn re-prefills the whole document — 7,999 then 8,020 tokens, growing by
exactly the conversation delta. Cached, turns 2–3 process **27 and 22 tokens**: the new
question and nothing else.

**A follow-up question costs ~30 seconds with caching and ~8.7 minutes without.**

## The confound is measured, not argued

Turn 1 is *identical work* in both arms — same document, same 7,976 tokens, full cold
prefill either way. It is therefore a direct measurement of the arm-order / page-cache
effect that invalidated the previous test:

**658.2 s vs 579.7 s — a 12% difference on identical work.**

That is the whole order effect, and it is ~135× smaller than the 16–18× being claimed.
It also runs the *right* way to be conservative about the mechanism: with `-ncmoe 40` the
expert weights stream from CPU memory every token, so the second arm inherits a warm page
cache, and 12% is what that is worth here.

**Correction to something I stated earlier.** I said running the no-cache arm first biased
the test *against* the caching hypothesis. That was backwards: running first means a *cold*
page cache, so the no-cache arm took the penalty and the cache arm (second) got the warm
advantage — biased *toward* the hypothesis. The conclusion survives anyway, because turn 1
puts a number on that advantage (12%) and 12% cannot produce 16×. Stated because the
reasoning was wrong even though the result holds.

## Correction: the 478 ms/token prefill figure was pessimistic by ~6×

`DS4_FLASH_P100_LOAD.md` recorded **478 ms/token** prefill and concluded *"a 4k-token context
costs ~32 minutes before the first output token."*

Measured here at real context depth:

| prompt tokens | prefill | ms/token |
|---|---|---|
| 7,976 | 579.7–658.2 s | **73–83** |
| 7,999 | 529.8 s | **63** |
| 8,020 | 513.0 s | **61** |
| 27 | 8.2 s | 302 |
| 22 | 5.9 s | 268 |

**Prefill runs at 61–83 ms/token at 8k, not 478.** The original figure came from a ~30-token
prompt, where fixed per-request overhead dominates and the per-token rate is meaningless —
visible here too, in the 268–302 ms/token on the tiny cached turns.

So an 8k document ingests in **~10 minutes, not ~64**. The "impractical without a prompt
cache" framing was directionally right but quantitatively off; the *real* argument for the
cache is that it removes the repeat cost entirely, not that a single prefill is unaffordable.

## Retrieval from 8k context works

Asked for node 33's maintenance window, the model located and quoted the correct section
verbatim:

> *"Section 33 describes Node 33. Reading Section 33: 'Node 33 of the cluster is provisioned
> with 32 GB of accelerator memory and sustains 199 tokens per second on the reference
> workload…'"*

Ground truth: 32 GB, 199 t/s. Exact match, from ~8k tokens of near-identical distractor
sections (70 sections differing only in numbers) — a deliberately hostile retrieval target.

**But `finish_reason: length` on both follow-ups.** `max_tokens=96` was chosen to make
prefill dominate, and it truncated the model mid-reasoning before it stated the final answer.
**Retrieval is verified; answer correctness is not.** The two are different claims and only
the first is supported here.

## DEFECT: the assistant replies were never fed back — the ~30 s figure is not a real turn

The token deltas give it away. Uncached: turn 1 → 2 is **+23 tokens**, turn 2 → 3 is **+21**.
A 96-token reply plus a ~20-token question cannot fit in 23 tokens. What fits is the question
plus the literal string `(empty)`.

Cause: the script's *display* parser reads `content` **and** `reasoning_content`, but its
*conversation builder* reads only `content`:

```python
t = json.load(open(p))['choices'][0]['message'].get('content') or ''
m.append({'role':'assistant','content': t or '(empty)'})
```

With `finish_reason: length` and all 96 tokens spent mid-reasoning, `content` is **empty** and
the whole reply lands in `reasoning_content`. Verified directly:

```
resp_cache_t1.json     content=0  reasoning=439  finish=length
resp_cache_t2.json     content=0  reasoning=402  finish=length
resp_nocache_t1.json   content=0  reasoning=439  finish=length
```

**The model was shown `[doc+Q1] → "(empty)" → [Q2] → "(empty)" → [Q3]`.** So the cached turns
prefilled 22–27 tokens because there was no prior reply to prefill.

### What survives, and what does not

**Survives — the uncached arm is fully representative.** It re-prefilled 7,999 and 8,020
tokens per turn. A real conversation would re-prefill *at least* that. The ~8.7-minute
per-turn penalty without caching is real.

**Does not survive — "~30 s per follow-up."** That is 8 s of prefill plus 96 truncated
decode tokens. A real turn also prefills the previous reply and decodes a substantive answer.

**Corrected estimate** (arithmetic from measured rates, *not* measured end-to-end):

| | uncached | cached |
|---|---|---|
| prefill | ~8,000 tok @ 63 ms → **~8.5 min** | ~140 tok @ ~280 ms → **~40 s** |
| decode (300-token answer @ **4.75 t/s warm**) | ~1.1 min | ~1.1 min |
| **per turn** | **~9.6 min** | **~1.7 min** |

*(Decode rate corrected 2026-08-02 — see `DS4_DECODE_WARMUP.md`. The 2.16 t/s used in the
first version of this table is a cold-cache first-draw figure; warm steady-state is 4.2–4.8
t/s. A multi-turn session is warm by definition after turn 1, so the warm rate is the right
one here. The conclusion is unchanged and slightly strengthened.)*

So the honest claim is: **caching removes the ~8.5-minute prefill penalty and leaves you
decode-bound at roughly 1.5–2 minutes per turn.** The ratio is ~5.6×, not the 16× the raw
measurement suggested, but the absolute saving — ~8.5 minutes every turn — is unchanged and is
the thing that matters.

### And it only fit under `-c 8192` because the replies were dropped

The document alone is 7,976 tokens against a 8,192 ceiling. With real 96-token replies
turn 2 would be ~8,116 and turn 3 ~8,234 — **over the limit**, triggering context shift,
which evicts the cached prefix and destroys the reuse being measured. With realistic
300-token answers it would blow the ceiling at turn 2.

**Practically: an 8k document at `-c 8192` sustains about one real follow-up before
eviction.** A usable research-companion session needs a larger `-c`, which costs KV memory
that this configuration does not obviously have spare. **Untested.**

## Practical verdict — viable, with caveats that matter

| workflow step | cost |
|---|---|
| model load | ~2.5 min (once per session) |
| ingest an 8k-token document | ~10 min (once per document) |
| each follow-up question | **~3 min, decode-bound** (estimated, see above) |
| without caching | ~11 min per follow-up |

A usable research/brainstorm loop on four 2016 GPUs running a 284B model every compatibility
table marks incompatible with 16 GB cards — provided you raise `-c` above 8192 and accept
minutes, not seconds, per turn.

This still **corrects the "not an agent backend" reading** of `DS4_FLASH_P100_LOAD.md`, which
assumed a 478 ms/token prefill on every turn. But the corrected margin is ~3.7×, not 16×.

Agent use remains unresolved and now looks *harder*, not easier: agent loops append tool
results mid-conversation, so context both mutates and grows fast — the two things that break
prefix reuse and hit the context ceiling. Nothing here measures that.

## Limits

- **K=1 per arm.** The 16–18× gap is far outside any plausible single-draw noise; the 12%
  turn-1 delta is not resolvable and is treated as an upper bound on the order effect, not a
  measurement of it.
- **One document shape**, synthetic, highly repetitive (70 near-identical sections). Real
  documents compress and tokenise differently.
- `max_tokens=96` truncated every answer. No claim about answer quality or correctness.
- Only linear chat growth was tested — strict prefix extension, the friendliest possible case
  for prefix caching.
- **Assistant replies were never fed back into the conversation** (see DEFECT above). The
  cached-turn cost is therefore a floor, not a realistic turn; the ~3 min corrected figure is
  arithmetic from measured rates, not an end-to-end measurement.
- Context limit is 8,192 against a 7,976-token document, and it only stayed under the ceiling
  *because* the replies were dropped. With real replies this configuration sustains roughly
  one follow-up before eviction. Not tested at a larger `-c`.
- `cache_prompt=false` still reused ~half the context at short lengths in the earlier test.
  At 8k it does not (7,999 of ~8,000 processed), so the control behaves correctly *here* —
  worth knowing that the flag's behaviour appears length-dependent.

## Provenance

- `.194:~/ds4_cache_long/` — `long.log`, `server_{cache,nocache}.log`, `doc.txt`,
  `resp_{arm}_t{1,2,3}.json`
- Script `~/ds4_cache_longctx.sh`; local copy `scratchpad/ds4_cache_longctx.sh`
- Prior/superseded: `DS4_PROMPTCACHE_INCONCLUSIVE.md`, `PREDICTIONS_ds4_promptcache.md`
- Method fixes carried in from that run: ordinal log parsing (no in-band markers), fresh
  server per arm, `import sys` in the wall-clock helper
