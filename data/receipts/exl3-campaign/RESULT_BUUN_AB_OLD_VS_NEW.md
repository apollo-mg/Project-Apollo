# Result -- buun `c9c52d71` vs `08826ad6` on 2x P100: +13% decode, and a prefill number that lies

**2026-09-20, `.73`** (2x Tesla P100, sm_60). Same model (`Qwen3.8-27B-Q6_K`), same flags,
**only the binary differs**. 548 commits apart (2026-09-04 -> 2026-09-19).

Fixed seed, `max_tokens: 200` so `predicted_n` is identical across runs and tok/s is comparable
rather than length-confounded. 9 requests per arm, **first discarded as warmup** (the
2026-09-20 rule: the first request after a model load is unreliable). Medians of the rest.
All figures are the server's **own** `timings`, measured server-side, so the fact that arm A
went through the wake proxy and arm B direct to `:8080` does not enter.

## Like-for-like (both processing all 34 prompt tokens)

| metric | OLD `c9c52d71` | NEW `08826ad6` | delta |
|---|---:|---:|---:|
| **decode tok/s** | 17.19 | **19.49** | **+13.4%** |
| prefill tok/s | 49.42 | 46.07 | -6.8% |
| prefill ms | 688.0 | 738.0 | +7.3% |
| **MTP acceptance** | **42.5%** (91/214) | **56.5%** (105/186) | **+14 pts** |

**The decode gain is explained by draft acceptance.** The new build drafts *less* (186 vs 214) and
accepts *more* (105 vs 91) for the same 200 predicted tokens -- more tokens per verification
round, so fewer target-model forward passes. Prefill is slightly slower, within the range that
n=7 medians cannot separate from noise.

## The cache advantage, which is real but is NOT a throughput change

On a **repeated** prefix the new build reuses the cache and the old one cannot (see
`RESULT_PROMPT_CACHE_BISTABILITY.md`: the old binary logs `cache-ram disabled`,
`fallback=live_only`, and never reports a cache hit):

| | tokens processed | cached | prefill ms |
|---|---:|---:|---:|
| OLD | **34** | 0 | 688.0 |
| NEW | **4** | 30 | **163.5** |

**4.2x less prefill wall time on a repeated prefix.**

## The trap: `prompt_per_second` is meaningless under caching

The first comparison drawn from these runs read **"prefill -50.5%"** (49.42 -> 24.47 tok/s), which
would have been reported as a serious regression. It is an artifact. With 30 of 34 tokens served
from cache the new build processes **four tokens**, and fixed per-request overhead dominates the
rate while the actual time falls by 76%. The rate looks halved precisely *because* the build got
faster.

**Rule: when a cache is in play, compare prefill WALL TIME at matched `prompt_n`, never
`prompt_per_second`.** Record `prompt_n` and `cache_n` beside any prefill figure, or the number
cannot be interpreted at all. The like-for-like row above was obtained by forcing
`cache_prompt: false` on the new build so both arms processed all 34 tokens.

## Caveats

- **n=7 and n=8 medians.** Good enough for a +13% decode difference, not for the -6.8% prefill.
- **One prompt, one shape**, 34 tokens in / 200 out. Long-context behaviour is unmeasured, and
  that is where the cache reuse would matter most.
- **MTP on for both arms**, which is the daily-driver config. With MTP off the decode comparison
  would likely narrow, since acceptance rate is where the gain comes from -- unmeasured.
- Decode was **19.50 with cache on and 19.49 with cache off**, so the cache affects prefill only.
  A useful internal consistency check.

## Operational finding: the proxy owns the server

`WP_START_CMD` is set and hardcodes `build_sm60_head/bin/llama-server` with the full daily-driver
flags. **Killing llama-server does not swap the binary -- the proxy immediately relaunches the old
one**, takes the VRAM, and any manually started replacement then dies with
`cudaMalloc failed: out of memory`. That is exactly how arm B failed on the first attempt, and an
earlier reading of the unit that concluded "managed mode, the proxy does not start the server" was
wrong.

**To swap binaries: stop `apollo-wake-proxy` first, verify the process is gone AND that VRAM has
actually fallen (both were checked the second time), then start the replacement.** Restarting the
proxy afterwards restores the daily driver by itself on the next request.

## Verdict

**The new build is worth taking for decode**, and the cache reuse is a further, larger win on any
workload with repeated prefixes -- which agentic multi-turn work is. Against that,
`RESULT_PROMPT_CACHE_BISTABILITY.md` shows the cache path is non-deterministic when speculative
decoding is on. For chat use that is irrelevant. For the corpus v2 campaign it is moot, because
MTP is off there anyway -- and with MTP off the warm-cache path measured clean.
