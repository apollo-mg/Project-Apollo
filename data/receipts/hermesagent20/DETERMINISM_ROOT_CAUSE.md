# Temperature-0 nondeterminism — TWO independent causes, one upstream, one VBR-specific

**2026-07-27.** Node `.73`, dual Tesla P100 (sm_60), 1063 MHz / 150 W.
Model `Hermes3.6-35B-A3B-Uncensored-Genesis-V5-APEX`.
Prompt fixed, `temperature 0`, `top_k 1`, `top_p 1.0`, `seed 1234`, `max_tokens 800`,
`finish_reason=length` on every draw. Completions compared **byte-for-byte**.

> **Supersedes the first version of this file**, which concluded "concurrent batched
> decoding" was the whole story. That was wrong: a slot-isolation test showed slot identity
> alone is sufficient under VBR, with no concurrency at all. Both the original claim and the
> correction are kept here because the sequence is the point.

## Effect 1 — concurrent batched decoding. **PRESENT UPSTREAM.**

| build | KV | condition | distinct outputs | vs idle baseline |
|---|---|---|---|---|
| `buun_vbr` | vbr | sequential idle | 1 of 5 | baseline `b4b78baa8b92` |
| `buun_vbr` | vbr | **C=2** | 3 of 6 | **6/6 differ** |
| `buun_vbr` | vbr | C=2 at **`-np 1`** | **1 of 6** | **0/6 differ** |
| **upstream `0e4a03622`** | f16 | sequential idle | 1 of 4 | baseline `b1dfc8fab35c` |
| **upstream `0e4a03622`** | f16 | **C=2** | **4 of 6** | **6/6 differ** |

Genuine `ggml-org/llama.cpp` (plus only the sm_60 FAST_FP16 carve-out) reproduces it.
**Answer to "is this problem upstream too?" — yes, this half is.**

The `-np 1` row is the mechanism control: two concurrent HTTP requests **queue** (timings
alternate 16.6 s / 33.2 s) and every completion returns byte-identical. Two sequences
decoding in one fused batch change the batch's shape and contents, which changes GEMM
tiling / reduction order, which changes FP rounding, which perturbs logits — and at
temperature 0 the sampler is `argmax`, so a near-tie flips and diverges through the KV cache.

## Effect 2 — slot identity. **VBR-SPECIFIC. Not upstream, not the fork generally.**

Requests pinned to a slot via `id_slot`, issued **sequentially** — only one slot ever
decoding, so concurrency is fully removed:

| build | KV | slot 0 | slot 1 | agree? |
|---|---|---|---|---|
| upstream `0e4a03622` | f16 | `b1dfc8fab35c` | `b1dfc8fab35c` | **yes** |
| `buun_vbr` | **f16** | `b4b78baa8b92` | `b4b78baa8b92` | **yes** |
| `buun_vbr` | **vbr** | `b4b78baa8b92` ×3 | `ad088b9aa24d` ×3 | **NO** |

Same fork, same flags, **only the KV codec changed.** Each slot is perfectly reproducible
within itself (3/3 identical); the two slots disagree with each other.

**Slot 0 under VBR matches the true-f16 reference byte-for-byte** (`b4b78baa8b92`, also what
`buun_vbr -ctk f16` produces on both slots). So slot 0 is right and **slot 1 is the
deviant** — 3208 chars vs 3137, diverging in content, not merely length.

**`/slots` reports `kv_bpv = 16.0` on BOTH slots.**

### Refined 2026-07-27 evening — it is FIRST-USE ordering, and no degradation is involved

buun's read was *"if you are running them concurrently, they will degrade at different
orders… it likely swapped some layers over to turbo8 as the context filled."* Tested with
`-v`, and **the degradation half is not what is happening** — but the asymmetry is real and
sharper than "slot identity."

Three fresh-server runs with `cache_prompt=false` (every request re-prefills from scratch,
so the prompt cache is out of the picture):

| run | slot order | result |
|---|---|---|
| A | `0, 1` | s0 `b4b78baa8b92` · s1 `ad088b9aa24d` |
| B | `1, 0` | s1 `b4b78baa8b92` · s0 `ad088b9aa24d` |
| C | `0, 1, 0` | s0 `b4b78…` · s1 `ad088…` · s0 **`b4b78…`** |
| D | `1, 0, 1` | s1 `b4b78…` · s0 `ad088…` · s1 **`b4b78…`** |

C and D falsify both simpler readings. Not slot identity (B and D give slot 1 the *correct*
hash, A and C give it the deviant one). Not request order (the third request returns to the
first hash). The rule that fits all four:

> **The first slot exercised after server start produces f16-exact output. Every other slot
> produces a different output, stable per slot for the remainder of the server's life.**

**No degradation occurred.** In 57,986 verbose lines: zero demote / downgrade / evict /
reclaim events; the only `degrad` hits are setup (`vbr_load_degrade_order: 100 baked steps`,
`vbr_floor_clamp_order`). Utilisation was **`projected 44.00 / budget 2560.00 MiB` — 1.7 %**.
There was never any pressure to degrade under.

So the divergence is not a tier swap. It is an asymmetry in VBR's **per-slot state
established at first use**, while every slot still reports `kv_bpv 16.0` and the
first-used slot matches true f16 byte-for-byte.

**Candidate mechanisms (speculative, not tested):** lazy VMM page mapping — the log shows
`VBR VMM pool #0: 324.00 MiB VA reserved, 4.00 MiB mapped up front` plus
`vbr_shrink_watermark` remapping `1792 → 1024 → 256 → 0` cells — or the
`VBR f16 sink-stash: 128 rows per (layer,side)` being populated on first use. Both would
make "which slot touched the pool first" a real variable. Naming these as leads, not claims.

**Reproducer for buun:** `slot_probe.py --slots 1,0,1 --reps 1 --no-cache-prompt` against a
freshly started server. Three requests, ~60 s, no benchmark involved.

## buun's diagnostic question: quality issue, or temp ignored on other slots?

*"If it's a subtle mathematical difference then we have a quality issue. If it's just
ignoring the temp setting on other slots, then that's a bug but not a bad one per se."*

**It is the subtle mathematical difference.** Sampling is ruled out by exact repetition:

- Slot 1 returns `ad088b9aa24d` on **3 of 3** draws — an 800-token completion reproducing
  byte-for-byte. Sampling at any temperature above 0 cannot do that.
- Under C=2, individual hashes repeat too (`beaf42775a66` ×3 of 6 on tensor split).
- The divergence looks like a near-tie flip, not a sampled token: at char 392,
  `Snake representation (list of coordinates)` vs
  `Snake (represented as a list of coordinates)` — semantically equivalent, locally
  high-probability, deep into the text rather than at the start.

Every configuration is deterministic *given* its batch/slot context. Nothing is ignoring
temperature; the arithmetic differs.

## What this retires

- **`-sm tensor` exonerated.** Both split modes are deterministic when idle and both break
  under concurrency. They produce *different but individually stable* outputs
  (`b4b78baa8b92` vs `b031af29fd93`) — split mode changes the arithmetic without
  destabilising it. Tensor split keeps its performance advantage.
- **MTP exonerated** — verified off (no draft flags; server logs `no implementations
  specified for speculative decoding`).
- Predictions logged before the run — Claude ~40 %, Mark's public "that's my bet", buun's
  "tensor splitting then" — were **all wrong**.

## The methodological failure

Six arms × 3–6 draws measured **scores** from an agent benchmark. Score is a lossy hash of
the output. Across all 36 (arm, scenario) groups ever collected: **33 had an identical score
hiding different output; 0 ever produced identical output.** Every "collapse" in the six-arm
table was scoring granularity. The eliminations survive (each asked "does variance persist?"
and it did, at 100 %); the collapse readings do not.

buun got here in one line — *"is the output identical on both or not — did he capture the
output?"* A byte-diff answers in ten minutes what score-based K-and-collapse designs could
not answer in hours.

## Operational consequences

- **`-np 1` is a reproducibility guarantee on this stack; `-np > 1` is not**, at any
  temperature, on **upstream or any fork**. Serve single-slot for regression tests, quant/KV
  A/Bs, and greedy determinism controls.
- **Under VBR specifically, `-np > 1` also means some requests get arithmetic that differs
  from f16 while reporting `kv_bpv 16.0`.** Worth a real KLD check per slot.
- Every agent benchmark this project ran against a `-np 2` server sampled an uncontrolled
  variable, temp 0 included. `.194`'s HumanEval+ work runs `-np 1` and is unaffected.

## Apparatus

- `HermesAgent-20/determinism_probe.py` — N sequential draws, byte-diff, first-divergence index
- `HermesAgent-20/concurrency_probe.py` — C in flight × R rounds vs an idle baseline
- `HermesAgent-20/slot_probe.py` — `id_slot`-pinned sequential draws, separates slot from batching
- Raw completions under `HermesAgent-20/determinism/<label>/`

**Harness hazard found en route:** `hermes_server_ctl.sh` kills only
`buun_vbr/build/bin/llama-server` by pattern, so with the upstream binary serving port 8082
it killed nothing, the fork failed to bind, and the health check went green in 1 s against
the *surviving upstream server*. Caught by checking which binary was actually serving before
running probes. Kill by explicit PID from `ps -eo pid,comm`, and always verify the serving
binary, not just `/health`.
