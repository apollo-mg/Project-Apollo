# Speculative Decoding Test Protocol v1

**2026-08-24.** Standing method for every speculation measurement in this project. Written
because four separate runs this week produced numbers that could not be compared to each other.

## Why this exists

`S2` (DFlash on Pascal) and the DFlash2 sweep both produced correct numbers that were **not
comparable**: different split modes, different targets, different boxes, one prose prompt each.
`RESULT_SPLIT_X_MTP` had to restate `NOTE_PRECISION_VS_SPECULATION`'s ratios from same-harness
data for exactly this reason.

## The claim this protocol is designed to support

**Throughput gain = acceptance rate × (cost of a rejected draft).** `S2` recorded the decisive
observation: *at ~29 % acceptance one architecture is at its fastest and the other is slower than
not speculating.* Acceptance alone predicts nothing. Both terms must be reported, always.

## Mandatory reporting

Every speculation number carries all of:

| field | why |
|---|---|
| **target model + exact quant file** | acceptance is quant-sensitive: MTP 65.7 % at IQ2/IQ3 vs 70.7–71.5 % at Q6_K |
| **draft head + quant** | a BF16 vs Q8_0 draft is a 1.7 GB difference and decides whether it loads at all |
| **`--spec-draft-n-max`** | Pascal peaks at n=3 and inverts; RDNA4 climbs to n=15 |
| **split mode** | `-sm tensor` is 1.63× `-sm layer` on 2×P100 *before* speculation |
| **node, clock, power** | 1063 MHz / 150 W pinned on this fleet |
| **acceptance rate AND mean accepted length** | the two halves of the trade |
| **baseline t/s measured in the same session** | never carried across runs |
| **prompt domain** | see below — this is the axis we have been ignoring |

## Prompt set — three domains, not one

Every arm runs all three. Acceptance is expected to differ sharply by domain, and every
speculation number this project holds was taken on **prose only**.

| id | domain | rationale |
|---|---|---|
| `P-PROSE` | 400-word technical explanation of KV cache layout | matches all prior receipts, preserves continuity |
| `P-CODE` | write a Python class with type hints, docstrings and error handling | syntax is highly predictable; Mark recalls ~89 % MTP acceptance on code |
| `P-STRUCT` | emit a 40-line JSON config with nested objects | maximally predictable — the acceptance ceiling |

**Prediction to be scored, not assumed:** acceptance rises PROSE < CODE < STRUCT, and the
break-even point moves with it — a method that loses on prose may win on code.

## Arms

Always include **`off`** measured in the same session, on the same server binary. Three
independent measurements of the Q6_K baseline landed at 13.24 / 13.25 / 13.26 t/s, so a
same-session baseline is cheap and removes all drift arguments.

Sweep `n ∈ {3, 5, 7}` on Pascal (S2: peaks at 3, inverts after). Extend to 15 only on RDNA4.

## Rules

- **3 reps per cell, report the best**; speculation variance is high (`RESULT_SPLIT_X_MTP`
  measured 40–58 % spread on speculative arms vs ~5 % on non-speculative).
- **Persist per item, flushed and fsynced** — standing rule.
- **Verify the drafter actually engaged.** A slow arm with 0 % acceptance is a broken config, not
  a result. Read `draft acceptance = ...` from the server log every time.
- **Check VRAM is free before launching.** A stale server cost six benchmark arms on 2026-08-23.
- **Never compare across split modes or targets.** If the target changes, the baseline changes.

## Open question this protocol is built to answer

On Pascal, MTP ≈ DFlash1 (51.31 vs 52.28 t/s at n=3, `S2`) and **DFlash2 is 0.67× — slower than
not speculating**. MTP heads ship inside the model file and cost 1.28 GiB as a standalone head
against DFlash2's 2.18 GiB. **Hypothesis (Mark): on Pascal, MTP is the right choice.** The
protocol exists to settle that with matched targets and all three domains.
