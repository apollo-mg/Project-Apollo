# The price of determinism — measured

**2026-07-27.** `.73`, dual Tesla P100 (sm_60), 1063 MHz / 150 W, `buun_vbr`,
`Hermes3.6-35B-A3B-Genesis-V5-APEX` (MoE, 256 experts / 8 active), `-ctk vbr -ctv vbr`,
`-sm tensor -ts 1,1`, `-c 32768 -b 1024 -ub 512`. `/completion`, raw prompt, `temperature 0`,
`top_k 1`, `seed 1234`.

Three state channels make temp-0 output depend on server history (see
`DETERMINISM_ROOT_CAUSE.md`, `PREFIX_CACHE_CHANGES_OUTPUT.md`). Two have config workarounds:
`-np 1` closes concurrency **and** the VBR slot bug; `cache_prompt=false` closes prefix reuse.
This measures what each costs.

## Price of `-np 1`

| workload | `-np 2` (default) | `-np 1` | price |
|---|---|---|---|
| single-shot, sequential | 27.0 s | 27.1 s | **none** |
| 5-turn conversation, cache on | 31.4 s | 31.4 s | **none** |
| 5-turn conversation, cache off | 163.7 s | 163.3 s | **none** |
| 2 concurrent, **prefill-heavy** (3.7 k prompt / 300 gen) | 48.9 s | 51.6 s | 1.06× |
| 2 concurrent, **decode-heavy** (14 tok prompt / 800 gen) | **22.3 s** | 33.7 s | **1.51×** |

**`-np 1` is free unless requests actually overlap.** Sequential work is identical to within
noise (27.0 vs 27.1 s; 31.4 vs 31.4 s; 163.7 vs 163.3 s).

**The concurrency cost is entirely workload-shaped.** Batching helps *decode* (memory-bound),
not *prefill* (compute-bound, already saturating). Measured as the speedup from issuing two
requests concurrently rather than back-to-back:

| | `-np 2` | `-np 1` |
|---|---|---|
| prefill-heavy | 1.08× | 1.01× |
| decode-heavy | **1.51×** | 1.00× |

At `-np 1` concurrent requests queue, so the speedup is 1.00× by construction — the second
request waits (33.7 s wall, individual times 16.9 / 33.7).

> **Correction to a first-pass measurement.** An earlier version issued two *identical*
> concurrent prompts and found `-np 1` *faster* (31.7 s vs 53.9 s). That was an artifact: the
> queued second request hit the first's prompt cache. It measured cache reuse, not batching.
> The table above uses two **different** prompts with `cache_prompt=false`, so neither request
> can reuse the other's work.

## Price of `cache_prompt=false`

| workload | cache on | cache off | price |
|---|---|---|---|
| single-shot, first time | 27.0 s | 27.0 s | **none** |
| single-shot, repeated | **4.9 s** | 26.9 s | **5.5×** |
| 5-turn conversation | **31.4 s** | 163.3 s | **5.2×** |

Per-turn prefill tokens tell the story directly:

- cache **on**: `[516, 13, 15, 15, 15]` — only the new user text
- cache **off**: `[4687, 4797, 5111, 5425, 5739]` — the whole conversation, every turn

This is the expensive carve-out, and it is the one llama.cpp enables by default
(`common/common.h:622`, `cache_prompt = true`).

## The nuance that makes it cheap in practice

**Repeated identical requests are reproducible with the cache ON.** Verified in both configs:
workload A ran the same prompt twice with `cache_prompt=true` and returned byte-identical
output (`reproducible=True`), while taking 4.9 s instead of 27.0 s on the repeat.

The cache only breaks reproducibility when **different** prompts interleave, because then the
cache state at request N depends on what ran before it. So:

- **K-repeat benchmarks of a fixed prompt** → leave the cache on. Free 5.5× and still exact.
- **Suites that interleave different prompts** (HermesAgent-20 does) → `cache_prompt=false`,
  or reset state between items.

## Recommended profiles

| use case | config | cost vs default |
|---|---|---|
| single-user local, interactive | `-np 1`, cache on | **zero** |
| K-repeat benchmark, fixed prompt | `-np 1`, cache on | **zero** |
| benchmark interleaving prompts | `-np 1`, `cache_prompt=false` | up to 5.2× on multi-turn |
| multi-user serving | `-np 2`, cache on | fastest, **not reproducible** |

**Headline:** for single-user local inference — the overwhelmingly common case — determinism
costs **nothing**. `-np 1` is free unless requests overlap, and the cache can stay on for
repeated-identical work. The price only appears when serving concurrent users (up to 1.51×)
or when a measurement run interleaves different prompts (up to 5.2×).

## Caveats

- One model, one hardware pair, `-b 1024 -ub 512`. The decode/prefill balance that determines
  the batching benefit is architecture- and flag-dependent.
- Workloads ran in sequence against a warm server, so workload B's turn-1 prefill (516 tok)
  benefited from workload A's cache. Both configs ran the identical sequence, so the
  comparison is symmetric, but the absolute turn-1 figure is optimistic.
- 2 concurrent requests only. Batching gains typically grow with concurrency; a 4- or
  8-way test would likely widen the `-np 2` advantage on decode-heavy work.
- `/slots ... action=erase` returns HTTP 501 on this build, so cache state could not be
  cleared between phases — only reset by restarting the server.

Apparatus: `HermesAgent-20/price_of_determinism.py`, `HermesAgent-20/concurrency_price.py`.
