Separate from the Pascal qualification: while testing determinism on `08826ad6` I hit a
reproducible bug where the same prompt with the same seed returns two different completions,
strictly alternating, once the prompt cache starts hitting.

**Repro** (2x P100 sm_60, CUDA 12.4, but I doubt the arch matters)

```
llama-server -m Qwen3.8-27B-Q6_K.gguf -ngl 99 -c 262144 \
  -ctk vbr -ctv vbr --vbr-floor t2 --vbr-vram auto \
  -np 1 -fit off -sm tensor -fa on \
  --spec-type draft-mtp --draft-max 3 --jinja --kv-unified
```

Fresh server, then POST the same 34-token prompt 10 times with a fixed seed
(temp 1.0 / top_p 0.95 / top_k 20, max_tokens 300):

```
[ 1] ff82d31f  len=1354  finish=length  cached_tokens=0
[ 2] 802ada7a  len=1312  finish=stop    cached_tokens=30
[ 3] ff82d31f  len=1354  finish=length  cached_tokens=30
[ 4] 802ada7a  len=1312  finish=stop    cached_tokens=30
... alternates cleanly to [10]
```

Request 1 misses the cache, every request after hits 30 of 34 tokens, and from there the output
flips between exactly two completions on odd and even requests. Not drift, not a spread: two
states, period 2, no exceptions across 14 consecutive requests in the first run I did.

**It needs speculative decoding.** Drop `--spec-type draft-mtp --draft-max 3` and keep everything
else identical:

```
9 of 9 byte-identical, 8 of them at cached_tokens=30
```

Including the cold first request. So the warm-cache path is deterministic on its own; it is cache
reuse plus MTP together that diverges.

**Why it may look new rather than broken.** On my previous build (`c9c52d71`) the cache never
engaged at all, `cached_tokens=0` on every request, and the log said:

```
W load_model: automatic dynamic VBR host caching fallback=live_only
   reason=artifact_topology_unavailable store_status=unavailable; cache-ram disabled
E slot: MTP checkpoint companion skipped: target=... draft=... spec=... state-ready=1
```

`08826ad6` emits neither line, so I think this is a newly reachable path rather than a
regression, and the short prompt is probably why I am seeing it: `30da59942` mentions allowing
short positive host-prefix matches without the source-coverage cutoff, and mine is 34 tokens.
`c7f114d34` (reuse active historical prefixes with checked MTP state) looks like the other half.
I have not bisected, those are just the commit messages that matched.

**Ruled out on my end**

- Not VBR precision. `/slots` reports `kv_bpv: 16.0` in both cases, since `--vbr-entry` defaults
  to f16 and a 34-token prompt never pushes it toward the floor. An f16 run reproduces the same
  two hashes exactly.
- Not the `computation_frontier_ratchet`. All counters stay at zero and `read_path` stays
  `legacy` across a warm batch.

Workaround if anyone needs it: `cache_prompt: false` on the request. Worth noting that seems to
suppress caching in that slot persistently rather than just for the one request, which is
convenient but surprising.

Happy to run anything else on this, including a bisect if it would help. Raw numbers for all four
arms are saved if you want them.

*Posted by my agent (Claude Opus 5) on my behalf. The hardware and the runs are mine; I reviewed this before it went out.*

---

**FOLLOW-UP (pending when the above was sent): it is not split-mode specific, and layer split is worse.**

Same build, same flags, MTP on, only `-sm tensor` swapped for `-sm layer`:

```
[1] 6eb36d5b len=1297 cached=0     [2] 109df7fb len=1190 cached=30
[3] 5602b694 len=1387 cached=30    [4] 109df7fb len=1190 cached=30
[5] 5a93cd32 len=1387 cached=30    [6] 109df7fb len=1190 cached=30
[7] 6cc37ea6 len=1281 cached=30    [8] 109df7fb len=1190 cached=30
[9] a78a05e1 len=1361 cached=30
```

Six distinct outputs over nine requests, against two under tensor split. The even-numbered
requests all land on the same completion and the odd ones are all different, though with n=9
I would not lean on that structure -- it could just be that most requests vary and the even ones
coincided. The part I would lean on is that layer split is affected too, and produces more
variation rather than less.

No layer-specific warnings in the server log.
