# Drafter architecture buys cost, and changes what the drafter is good at

*MTP head vs DFlash block-diffusion drafter: same target, same prompts, seven arms.*

**The portable finding is the content split, not the multiplier.** DFlash wins code, SQL,
JSON, regex and lists; the MTP head wins prose, story, repetition and translation — replicated
across three independent depths. That is architectural and should transfer. The 1.34–1.40x
speed advantage is a fact about this GPU and this model pair and should not.

**2026-08-15, RX 9070 XT (RDNA4, ROCm).** Target `unsloth/Qwen3.5-9B-MTP-GGUF` `Q8_0`
(9.11 GiB), drafter `AtomicChat/Qwen3.5-9B-DFlash-GGUF` `Q8_0` (1.29 GiB). Build:
`moe-cache-test` HIP, `-ngl 99 -c 8192 --jinja`, temp 0 / top_k 1 / seed 1234, 12 prompts
x 2 reps per arm. Raw: `raw/showdown.log`, `raw/dflash_*.json`.

**Why one target file for everything.** unsloth's MTP variant carries the head inside the
file (9.11 GiB against 8.87 for the plain build — the delta *is* the head), and the same file
serves as the DFlash target. So every arm below runs a byte-identical target and the drafter
is the only variable. The idle-head cost was checked rather than assumed: `off` measured
**55.27 t/s** on the MTP target against **55.16 t/s** on the plain one, 0.2 % apart. The head
costs nothing when `--spec-type` is absent.

## What DFlash actually is

Not a model. `Qwen3.5-9B-DFlash` is a **1.3 B, 6-layer `DFlashDraftModel`** — the "9B" names
the model it drafts *for*. Header: `dflash.block_size = 16`,
`tokenizer.ggml.mask_token_id = 248077`, `dflash.target_layers = [2,6,10,14,18,22,26,30]`,
sliding window 4096 with pattern `[T,T,T,T,T,F]`. It denoises a masked block conditioned on
hidden states pulled from 8 layers of the target.

It is **lossless**. `common.h:372` groups `DRAFT_DFLASH` with `DRAFT_MTP` and `DRAFT_EAGLE3`,
and it is a `common_speculative_impl` — standard verify-and-reject. The diffusion is only in
how the proposal is *generated*; acceptance is exact. So quantizing a DFlash drafter costs
speed and nothing else, exactly like an MTP head.

## Results

| arm | median t/s | mean t/s | x base (med) | acceptance | drafted | accepted |
|---|---:|---:|---:|---:|---:|---:|
| `off` | 55.27 | 55.24 | 1.00x | — | — | — |
| `mtp_n3` | 107.95 | 106.82 | 1.95x | 77.49 % | 6,899 | 5,346 |
| `mtp_n7` | 104.53 | 104.57 | 1.89x | 53.15 % | 11,319 | 6,016 |
| `mtp_n15` | 76.35 | 77.98 | 1.38x | 29.03 % | 21,340 | 6,196 |
| `dfl_n3` | 116.68 | 113.48 | 2.11x | 76.79 % | 6,938 | 5,328 |
| `dfl_n7` | 140.03 | 137.21 | 2.53x | 52.86 % | 11,378 | 6,014 |
| `dfl_n15` | 150.66 | 142.70 | 2.73x | 29.93 % | 20,840 | 6,238 |

**The curves go opposite directions.** MTP peaks at or below the stock default of 3 and loses
29 % by depth 15. DFlash climbs monotonically. They never cross — DFlash leads at every depth
tested. That ordering is monotone across three depths and is not sensitive to any of what
follows.

### Which statistic, and why it matters here

`dfl_n15` is the one arm where median and mean disagree materially — 150.66 vs 142.70, a
5.6 % gap, against ≤2.8 % everywhere else. Its per-prompt throughput ranges **44.35 to
286.58 t/s** (stdev 55.48, versus 0.74 for `off`). So the headline ratio depends on the
choice:

| comparison | by median | by mean |
|---|---:|---:|
| best DFlash vs best MTP | 1.40x | 1.34x |
| DFlash n=3 -> n=15 | +29 % | +26 % |

**Quote the range: 1.34–1.40x, and +26–29 % for the flag.** The spread is not instrument
noise — reps are near-identical — it is genuine content dependence, and it is the same
architectural effect as the acceptance split below, surfacing in throughput:

| prompt | `dfl_n15` t/s | x off |
|---|---:|---:|
| list | 257.19 | **4.64x** |
| reason | 210.06 | 3.80x |
| math | 172.53 | 3.12x |
| regex | 156.53 | 2.83x |
| table | 154.58 | 2.79x |
| json | 151.53 | 2.73x |
| code | 122.14 | 2.28x |
| repeat | 120.23 | 2.17x |
| sql | 105.72 | 1.91x |
| translate | 90.59 | 1.64x |
| story | 88.28 | 1.59x |
| prose | 82.99 | **1.50x** |

**A 3.1x range between best and worst content type.** A single "DFlash is 2.7x" number is
close to meaningless without saying what you are generating.

### The actionable number

`--spec-draft-n-max` defaults to **3** (`common.h:325`). DFlash was trained at
`block_size=16` and `speculative.cpp` clamps to 15. **Raising the flag is worth 26–29 % on
this hardware and costs nothing.** Out of the box, DFlash runs at a fifth of its trained
block.

The same flag is actively harmful to MTP: 3 -> 15 costs it 29 %. **One default cannot serve
both drafters**, and llama.cpp currently applies the same default to both.

### Why depth helps one and hurts the other

Accepted tokens barely move with depth (MTP 5,346 -> 6,196; DFlash 5,328 -> 6,238) while
drafted tokens **triple** (6,899 -> 21,340). Useful lookahead is capped; depth past that is
waste. The two architectures pay for that waste differently:

- **MTP** emits one token per head pass, so depth *n* costs *n* sequential passes. The waste
  is paid in compute, linearly, and it overtakes the verification saving between n=3 and n=7.
- **DFlash** denoises up to 16 positions in **one** pass, so the waste is nearly free. Its
  cost is flat in depth, so even a 30 %-accepted block of 15 beats a 77 %-accepted block of 3.

## The correction: acceptance is NOT drafter-independent

Mid-run, on aggregates alone, I claimed the two drafters were interchangeable in quality:
77.49 vs 76.79, then 53.15 vs 52.86, then 29.03 vs 29.93 — matched to under 1 pp at all three
depths. **That was wrong, and the per-prompt data falsifies it.** The aggregates coincide
because the per-prompt differences cancel against this particular prompt mix.

Acceptance %, per prompt:

| prompt | mtp_n3 | dfl_n3 | mtp_n7 | dfl_n7 | mtp_n15 | dfl_n15 | favours |
|---|---:|---:|---:|---:|---:|---:|---|
| code | 70.6 | **82.5** | 47.4 | **59.5** | 23.7 | **30.5** | DFlash x3 |
| sql | 79.8 | **86.5** | 58.3 | **65.8** | 33.9 | **38.5** | DFlash x3 |
| json | 79.4 | **83.2** | 51.7 | **58.6** | 31.3 | **34.5** | DFlash x3 |
| regex | 78.0 | **79.2** | 57.8 | **59.5** | 33.5 | **36.2** | DFlash x3 |
| list | **96.3** | 94.0 | 87.5 | **91.1** | 54.3 | **77.3** | DFlash x2 |
| prose | **59.6** | 55.0 | **32.7** | 29.7 | **19.1** | 15.3 | MTP x3 |
| story | **67.2** | 60.0 | **41.9** | 30.8 | **18.3** | 17.7 | MTP x3 |
| repeat | **81.6** | 74.3 | **71.0** | 57.6 | **30.1** | 25.3 | MTP x3 |
| translate | **69.9** | 67.0 | 35.4 | **36.1** | **20.8** | 18.1 | MTP x2 |
| table | **81.6** | 80.4 | 54.2 | **58.7** | 29.2 | **35.3** | mixed |
| math | **86.5** | 86.1 | 64.9 | **66.0** | 38.3 | **41.5** | mixed |
| reason | **89.9** | 88.5 | **76.6** | 75.7 | 47.6 | **53.5** | mixed |

**The split is structural and replicates across three independent depths.** DFlash wins on
code, SQL, JSON, regex, lists. MTP wins on prose, story, repetition, translation. Largest
consistent gaps: `code` +11.9/+12.1/+6.8 to DFlash; `repeat` +7.3/+13.4/+4.8 to MTP.

That is exactly what the architectures predict. Block denoising proposes many positions
without letting them condition on each other, which is cheap when the continuation is
structurally determined — closing brackets, SQL keywords, list items, JSON punctuation — and
expensive when each token genuinely depends on the last, which is what narrative prose is.
The intra-block independence assumption is the diffusion quality tax, and here it is visible
as a **content-type split rather than a uniform penalty**.

**So the right claim is: drafter architecture buys cost AND changes what it is good at.** The
aggregate hid the second half entirely. A benchmark on code alone would have overstated
DFlash; one on prose alone would have called it a regression.

## Prediction scoring

Logged before the run at ~0.7 confidence on ordering:

| # | prediction | outcome |
|---|---|---|
| 1 | DFlash widens its lead as `n_max` rises | **CONFIRMED** — 8.1 % -> 34 % -> 97 % |
| 2 | MTP flattens or turns over | **CONFIRMED** — turned over at or below n=3 |
| 3 | The two curves cross somewhere | **FALSIFIED** — DFlash leads at every depth |
| 4 | (mid-run) acceptance is drafter-independent | **FALSIFIED** — aggregate coincidence only |

## Limits

- One target, one model family, one GPU. The *shape* is architectural; the numbers are not
  portable.
- 12 prompts x 2 reps. Reps are near-deterministic replays and add no independent information;
  they are kept only as a bistability detector. **8 of 72** prompt/arm cells flagged
  (6 spec arms x 12 prompts — an earlier draft said 36, which was wrong).
  The distribution is itself informative: **all 8 are MTP arms; not one DFlash cell is
  bistable.** DFlash reproduces bit-identically at temp 0, MTP does not.

  | prompt | bistable in |
  |---|---|
  | table | mtp_n3, mtp_n7, mtp_n15 |
  | code | mtp_n3, mtp_n15 |
  | prose | mtp_n3, mtp_n7 |
  | translate | mtp_n3 |

  `code` carries the largest content-split gap, so it was checked directly: `mtp_n3` swings
  70.1 % -> 71.1 % between reps (**1.0 pp**) while `dfl_n3` is bit-identical (227/275 both
  reps). A 1.0 pp wobble does not threaten an 11.9 pp gap. This is a different situation from
  `headlab`, where the within-arm swing was 5.4 pp against a 1.86 pp effect.
- Only three depths. The MTP peak is at or below 3 and was not bracketed from below; n=1 and
  n=2 were not run, so "peaks at 3" is an upper bound on the peak location.
- Prompts are 320 tokens. Acceptance may behave differently over long generations where the
  target's own context grows.
- `dfl_n15` clamps to the trained `block_size-1`. Nothing here says what a drafter trained at
  a larger block would do.
