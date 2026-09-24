# Pre-registration — MTP time-to-completion for agents, with prompt caching ON

**2026-09-24, written before any arm.** RX 9070 XT, buun `38ada0e1b`, runner
`argus/run_mtp_agentic.sh cache`. Companion to `RESULT_MTP_AGENTIC.md`.

## Question

`RESULT_MTP_AGENTIC.md` measured *outcomes* with the prompt cache OFF. Each turn re-prefilled
10-15k tokens, which hid MTP's decode speed (per-item times came out about equal). Mark's framing: when
MTP only changes the path, the cost is time, and MTP's speed may more than pay for it. **Does MTP
shorten real end-to-end agent tasks when the server runs the way people deploy it (cache on)?**

**Prior art checked:** `ledger_precheck.py "MTP speculative end-to-end agent time to completion prompt
cache"` -> found:
- the cache x speculation output instability (INDEX L33, L36, L104: warm cache + MTP alternates between
  2+ outputs);
- MTP decode speedups on single requests (`battle16gb/`, `exl3` receipts).

**Nothing measures end-to-end agent task time.** That is what this adds.

## Setup

Identical to `PREREG_MTP_AGENTIC.md`, with three exceptions:
- **The prompt cache is ON** (no `--no-cache-prompt`), as in normal serving.
- Output goes to `argus/runs/mtpag_cache`.
- **The calendar is Thursday 2026-09-24** (`TZ=Etc/GMT+12`, pinned for the run), which matches the
  fixture's Thursday anchor. The outcome run's agent saw Wednesday, so **outcomes are not comparable
  across the two runs, only within each**.

Arms `OFF-s1, MTP-s1, OFF-s2, MTP-s2, OFF-s3, MTP-s3`, 40 items each, pristine agent-home per item.
With the cache on, the MTP arm's outputs are known to be unstable (bistable). The OFF arm should be
deterministic.

## Primary metric: per-item time to completion (driver `secs`)

- Per item-seed, `r = secs(MTP) / secs(OFF)` at the same seed. Per item, the mean of `log r` over seeds.
- Report the **geometric-mean ratio** with an item-level 95 % t-CI and a sign-flip permutation p
  (Monte Carlo 1e6 if more than 22 items are non-zero).
- **Timeouts:** counted at their limit (2,400 s), and listed per item as records.

| outcome | reading |
|---|---|
| geo-mean ratio < 1, CI excludes 1 | MTP completes agent tasks faster |
| CI includes 1 | no end-to-end speed benefit shown |
| ratio > 1, CI excludes 1 | MTP's detours cost more time than its decode speed saves |

**Prediction:** MTP faster, geo-mean ratio in **[0.60, 0.85]**, confidence **0.60**. Reasoning: decode is
about 2x, but prefill of new turn content, tool latency and harness time are not accelerated.

## Secondary (descriptive)

- **Expected time to success** per arm = total secs / passes, with an item-bootstrap CI of the MTP/OFF
  ratio. This is Mark's "if it errors more but is faster" metric for retryable work.
- Pass rates per arm. These are noisy for MTP under the cache (bistability), so they are **not** an
  outcome test. The outcome question stays with `RESULT_MTP_AGENTIC.md`.
- Server-side: prefill vs decode time, prompt-cache hit tokens, draft acceptance.
- **Consequence split** as in the outcome receipt: path-only change vs outcome flip.

## Not established

One model and quant, one card, one harness, `n-max 2`. Wall-clock time includes harness and tool
latency, which is the point: it is what a user waits for.

## Known before this run (the cache-OFF baseline, scored with this file's scorer)

`analyze_mtp_speed.py data/receipts/mtp-agentic/raw` on the outcome run gives:
- **geo-mean time ratio 0.947** (95 % CI 0.895-1.003, p = 0.061), so MTP is about 5 % faster end-to-end
  when every turn re-prefills.
- **Expected time to success 1.02x** (bootstrap CI 0.90-1.16), so the lower success rate cancels the
  speed.

The cache-ON run tests whether removing the re-prefill lets MTP's ~2x decode show up.
