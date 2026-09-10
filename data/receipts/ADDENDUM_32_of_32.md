# Addendum to `apollo-vbr-harness` — the band finished, and the headline moved

The tarball was packed at 31 of 32 cells. The 32nd landed and it **materially weakens the
number quoted in the README**. Correcting it unprompted.

## What changed

README said: *K > V at the layer level, **t = 6.65 on 14 df, p < 0.0001, sign 15/15***.

Complete 32-cell result: **mean K-V = +3.921e-07, t = 2.49 on 15 df, p = 0.0251, sign 15/16.**

Still significant, much weaker, and the pre-registered test is the 16-layer one — that is the
number that counts.

## Why: layer 63 inverts, and it is the most solid cell in the sweep

| | layer 63 | other 15 |
|---|---|---|
| K | 4.018e-07 | — |
| **V** | **2.093e-06** — most expensive cell in the band | — |
| K-V | **-1.691e-06** | +5.310e-07 |

`63v` is not noise. It has **z = 14.88** against the fp16 null, the **tightest SE of any cell**
(1.49e-07), and **8 of 8 chunks agree** — paired K-V = -1.69e-06 +/- 8.4e-08, t = -20.

Layer 63 is the **last full-attention KV layer**; `blk.64` is the MTP head. A uniquely
sensitive V cache in the final layer feeding the head is mechanistically plausible, but that
is a post-hoc reading of a discovered outlier, not a tested claim.

## The consequence matters more than the p-value

The README floated that the band might collapse to a single **K/V asymmetry constant**, making
a per-model scan unnecessary. **Layer 63 kills that in its simplest form.** A flat K/V rule
would be wrong by 3.2x in the opposite direction precisely at the layer whose V cache is the
most expensive in the model — an allocator following it would demote the single most sensitive
unit first.

What survives is narrower: **K > V generally, with terminal layer(s) special-cased.** Whether
"terminal" means *last* or *adjacent to the MTP head* is untested. The control that separates
them is the same band on a model without the MTP head in that position.

## Also corrected

`layer-pricing/INTERIM_BAND.md` in the tarball carried the wrong build hash in its header —
`e332b24`, which is the `.73` box. The band ran on `.194` under **`7d30a7244`**, same build as
the fidelity arms. `ENVIRONMENT.md` and the fidelity result were already correct.

`rho_half` at 32 cells: **0.591 +/- 0.090**, still failing the 0.90 bar; ~615 h to resolve the
fine ranking. That conclusion is unchanged.
