# PREREG — where does MTP stop paying? Speculation × concurrency

**Written 2026-09-07 before the run.**

## Why this has not been measured

Speculation trades **compute for latency**. At batch 1 decode is memory-bandwidth-bound with
compute to spare, so drafting is nearly free. Under concurrent load the machine becomes
compute-bound and every rejected draft token is work taken from another slot.

This corpus has both halves and never the product:

- `qwen38-mtp`: **1.68×** (30.25 → 50.85 t/s) — measured at `np=1`
- `splitscale/RESULT_NP.md`: `np=4` → 2.23× aggregate, `np=8` → 2.68× — sublinear, per-request
  degrades, "the signature of a shared bottleneck that batching cannot relieve"
- `RESULT_SPARK_SPECDECODE.md`: a 2.4:1 draft ratio is **0.75×** even at `np=1`

**Every MTP number in this corpus was taken at `np=1`.** If MTP inverts under load, those
figures do not describe a server with more than one user — including our own 1.68×.

## Design

`Qwen3.8-27B-GSQ-RCO-IQ3_XXS-mtp.gguf` (inline MTP head at `blk.64`), RX 9070 XT, gfx1201,
`buun-llama-cpp/build_rocm` `3823c9eb6`. `-ngl 99 -fa on`, **`-c` scaled as `2048 × np`** so
per-slot context is constant at 2048 across every cell — otherwise `np` changes two things.

8 cells: `np ∈ {1,2,4,8}` × MTP `{off, on}`. Each cell issues **`np` concurrent identical
requests**, temp 0, `max_tokens 300`. Metrics: aggregate tokens/s across all slots, and
per-request tokens/s.

MTP on = `--spec-type draft-mtp`; off = flag omitted (`--spec-type` defaults to `none`, which
`RESULT_SPARK_SPECDECODE.md` proved is a silent no-op trap — the MTP-on arms must show a
`draft acceptance` line or the cell is VOID).

## Predictions

| # | prediction | conf |
|---|---|---:|
| M-1 | `np=1` MTP-on reproduces a speedup ≥ 1.4× over MTP-off | 0.70 |
| M-2 | The MTP advantage **decreases monotonically** with `np` | 0.75 |
| M-3 | MTP **inverts** (aggregate MTP-on < MTP-off) at or before `np=8` | 0.55 |
| M-4 | Draft acceptance is roughly **flat** across `np` — batching changes the economics, not the draft quality | 0.70 |
| M-5 | MTP-on per-request latency stays better than MTP-off at every `np`, even where aggregate inverts — speculation buys latency, and that is what it is for | 0.45 |

**M-4 is the mechanism check.** If acceptance falls with `np`, something is interfering with
drafting itself and the compute-contention story is wrong.

**M-5 is the one that matters operationally.** If aggregate inverts while per-request stays
better, "turn MTP off under load" is only correct for throughput-optimising servers, and an
interactive fleet should keep it on. Those are opposite recommendations from the same data.

## Stopping rule

One pass over 8 cells, then score. Interim looks may abort only.
