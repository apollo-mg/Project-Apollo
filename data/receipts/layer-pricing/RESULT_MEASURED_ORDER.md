# A measured degrade order beats the generic one — 3.79x, in the regime where order can matter

**2026-08-26.** `.73`, 2× P100 sm_60, buun-llama-cpp `2714303` (`build_sm60_head`).
`Qwen3.5-4B-BF16`, `-c 4096 --chunks 8 -sm layer -fit off -ct vbr --vbr-floor t2`.
KLD against the same f16 base for both arms. Lower is better.

## The claim being tested

buun's runtime warns on every start with no order file:

> `vbr_load_degrade_order: no measured VBR degrade order for this arch/n_layer — using the
> generic cross-model order (a measured per-model order is better; set VBR_DEGRADE_ORDER=<file>)`

That is an assertion in shipping code. Our layer-pricing bands produce exactly the artifact it
asks for, so it is testable.

## Result

| budget | generic | measured | ratio | same-top-p |
|---|---:|---:|---:|---|
| 160M | 0.000000 | 0.000000 | — | 99.994 / 99.994 |
| **100M** | 0.001361 ± 0.000068 | **0.000359 ± 0.000018** | **3.79x** | 98.412 → **99.237** |
| 64M | 0.005044 ± 0.000745 | 0.004019 ± 0.000289 | 1.26x | 96.989 / 97.154 |

**The effect vanishes at both extremes, which is the validity check.** At 160M the budget is
generous enough that nothing is demoted and order is irrelevant. At 64M nearly everything is at
the floor and there is little left to order. It peaks in the middle of the degradation range —
the shape the mechanism predicts, and a stronger result than the headline ratio alone.

Error bars at 100M do not overlap.

## Order construction — sorted PER TIER, deliberately

Cells are sorted ascending by measured KLD **at each tier separately**, not by one global
ranking. Our own 27B data says the ranking is **not** transition-invariant (t8 vs t2
ρ=+0.247, n.s.), so a single global sort would contradict our own evidence.

## Caveats

- **Upper bound, not a pure ordering effect.** A custom `VBR_DEGRADE_ORDER` "carries no band
  guarantee, so it disables demand shedding", so the measured arm differs in more than
  ordering. Same limitation that capped the reversed-order control.
- **One model, one corpus.** Generality is untested — see below.

## REPLICATED on a second architecture (2026-08-26)

`Llama-3.2-3B-BF16`, 28 **dense** KV layers, matched to the 4B run on BOTH axes that matter:
ladder `f16 -> t8 -> t4`, floor `t2` (so the order's terminal tier sits ABOVE the floor).

| budget | generic | measured | ratio |
|---|---:|---:|---:|
| 400M | 0.000075 | 0.000072 | 1.04x |
| 260M | 0.012707 | 0.011245 | 1.13x |
| 180M | 0.036537 | 0.019082 | **1.91x** |
| 120M | 0.051419 | 0.020546 | **2.50x** |

**The finding generalizes across architectures** — 3.79x peak on a `qwen35` hybrid (8 KV
layers), 2.50x on a dense Llama (28 KV layers). Notably this is the ONLY layer-pricing result
so far that has survived an architecture change; terminal-V inverted, transition-invariance was
model-dependent, and three SNR mechanisms were falsified.

**The SHAPE differs and that is worth knowing.** The 4B peaks mid-range and vanishes at both
extremes. Llama climbs **monotonically as the budget tightens** (1.04 -> 1.13 -> 1.91 -> 2.50)
across the range tested. So "where in the budget range the order matters most" is
model-dependent even though "it matters" is not.

## Two matching axes, learned the hard way — THREE runs to get one comparison

The Llama replication was run three times. Each failure was an unexamined difference between
arms, not a property of the models:

| run | order ladder | floor | terminal vs floor | result |
|---|---|---|---|---|
| v1 | t8 -> **t2** | t2 | at floor | **0.16x** — measured 6x WORSE |
| v2 | t8 -> t4 | **t4** | at floor | 1.00x — flat, floor-saturated |
| **v3** | t8 -> t4 | **t2** | **above floor** | **2.50x** — replicates |

- **v1** compared a coarse ladder against a fine one. Skipping t4/t3 means the allocator drops
  cells two tiers at once at tight budgets; damage grew monotonically as budget tightened.
- **v2** fixed the ladder but set floor = terminal tier, so once the budget tightened every
  cell sat at the floor and order could not matter. Visible as 180M and 120M returning nearly
  identical KLD — floor saturation, not a null.
- **v3** matches both. Same measured order file as v2; **only the floor changed** and the
  answer went from 1.00x to 2.50x.

**Rule for any future order comparison: match the ladder AND the floor, and keep the order's
terminal tier strictly above the floor.** Enumerate what must be held constant before the
first run, not one axis per iteration.
## Appendix — the first (void) Llama attempt, kept for the record

A replication on `Llama-3.2-3B-BF16` (28 dense KV layers) showed the measured order up to
**6x WORSE** than generic (0.16x at 120M). That is not an architecture finding. The two order
files had different tier ladders:

| file | ladder |
|---|---|
| `measured_order_4b.txt` | f16 → t8 → **t4** (16 cells each) |
| `measured_order_llama3b.txt` | f16 → t8 → **t2** (56 cells each) |

The Llama file skips t4 and t3 entirely, because only t8 and t2 bands existed for that model.
At tight budgets the allocator has nothing between t8 and the floor and drops cells two tiers
at once, while the generic order steps gracefully. The damage grows monotonically as budget
tightens (1.04x → 0.82x → 0.29x → 0.16x), which is exactly that mechanism.

**A fine-grained order was compared against a coarse one and the difference attributed to
architecture.** Superseded by the matched v3 run above, which replicates at 2.50x.
