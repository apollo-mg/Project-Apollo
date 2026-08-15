# MTP head vs DFlash block-diffusion drafter: same target, same prompts, seven arms

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

| arm | t/s (median) | x base | acceptance | drafted | accepted |
|---|---:|---:|---:|---:|---:|
| `off` | 55.27 | 1.000x | — | — | — |
| `mtp_n3` | 107.95 | 1.953x | 77.49 % | 6,899 | 5,346 |
| `mtp_n7` | 104.53 | 1.891x | 53.15 % | 11,319 | 6,016 |
| `mtp_n15` | 76.35 | 1.381x | 29.03 % | 21,340 | 6,196 |
| `dfl_n3` | 116.68 | 2.111x | 76.79 % | 6,938 | 5,328 |
| `dfl_n7` | 140.03 | 2.533x | 52.86 % | 11,378 | 6,014 |
| `dfl_n15` | **150.66** | **2.726x** | 29.93 % | 20,840 | 6,238 |

**The curves go opposite directions.** MTP peaks at or below the stock default of 3 and loses
29 % by depth 15. DFlash climbs monotonically and gains 29 % from 3 to 15. They never cross —
DFlash leads at every depth tested.

**Best against best: 150.66 vs 107.95 = 1.40x.** At the stock default both are close
(116.68 vs 107.95, 1.08x), so the entire advantage is unlocked by a flag most people will
never change.

### The actionable number

`--spec-draft-n-max` defaults to **3** (`common.h:325`). DFlash was trained at
`block_size=16` and `speculative.cpp` clamps to 15. **Raising the flag is worth 29 % on this
hardware — 116.68 to 150.66 t/s — and costs nothing.** Out of the box, DFlash runs at a fifth
of its trained block.

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
  they are kept only as a bistability detector, and **8 of 36 prompt/arm cells flagged
  bistable** (rep0 != rep1). Per-prompt figures carry that noise. The content-type split
  survives it by replicating across three depths in the same direction, but individual cells
  should not be quoted to 0.1 pp.
- Only three depths. The MTP peak is at or below 3 and was not bracketed from below; n=1 and
  n=2 were not run, so "peaks at 3" is an upper bound on the peak location.
- Prompts are 320 tokens. Acceptance may behave differently over long generations where the
  target's own context grows.
- `dfl_n15` clamps to the trained `block_size-1`. Nothing here says what a drafter trained at
  a larger block would do.
