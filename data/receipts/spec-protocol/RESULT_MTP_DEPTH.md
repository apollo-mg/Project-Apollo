# The MTP optimum is load-dependent, and n=3 was never the peak

**2026-08-24**, `.194`, 2× P100 (sm_60), 1063 MHz / 150 W, `-sm tensor -fit off`, `-c 8192
-np 1`, f16 KV, buun `7d30a7244`. MTP head Q4_0 1.37 GB. Best of 3 per cell.
Raw `~/mtp_depth.log`.

**Registered before the run** (Mark): *"on Pascal+MTP the crossover will be load-dependent
between 2–4 drafts."* Falsifiable — if one `n` won every domain, the peak would be fixed.

## Result — t/s by `--spec-draft-n-max`

| target | n | acceptance | PROSE | CODE | STRUCT |
|---|---:|---:|---:|---:|---:|
| **IQ2_M** | 1 | **88.2 %** | **21.19** | 21.84 | 23.02 |
| | 2 | 74.9 % | 20.47 | 21.28 | 22.91 |
| | 3 | 74.9 % | 20.40 | 21.18 | 22.84 |
| | 4 | 64.5 % | 19.77 | **21.57** | **23.86** |
| | 5 | 59.6 % | 17.37 | 20.21 | 22.71 |
| **IQ4_XS** | 1 | **90.4 %** | **23.55** | **24.50** | 25.47 |
| | 2 | 82.1 % | 22.68 | 24.44 | **26.39** |
| | 3 | 82.1 % | 22.62 | 24.41 | 26.31 |
| | 4 | 64.4 % | 17.94 | 23.08 | 24.68 |
| | 5 | 59.4 % | 15.73 | 21.55 | 23.45 |

## Findings

**1. The hypothesis holds: no single `n` wins.** Peaks are IQ2_M {1, 4, 4} and IQ4_XS {1, 1, 2}
across PROSE/CODE/STRUCT. Prose peaks lowest, structured highest — the predicted gradient, and
the **opposite** of my counter-guess that n=2 would help prose most.

**2. "Pascal peaks at n=3" was a sampling artifact.** `S2` tested n ∈ {3,7,15}; the matrix tested
{3,5,7}. **Nobody sampled below 3.** n=1 is the fastest prose setting on both targets and the
fastest overall on IQ4_XS CODE. The claim was an artifact of the grid, not a property of the
hardware. `AFM-20` — a ladder that never varies below its floor is n=1 on everything under it.

**3. n=1 reaches 88.2–90.4 % acceptance**, matching Mark's recollection of ~89 % on
code — found at a depth that had never been measured.

**4. n=2 and n=3 are byte-identical.** Same acceptance to 5 decimals, same accepted/generated
counts (239/319 at IQ2_M, 248/302 at IQ4_XS), across all three domains and both targets.
**`--spec-draft-n-max 3` is producing exactly the n=2 behaviour.** That is an off-by-one or a
clamp in the draft path, not a measurement coincidence — worth reporting to buun.

**5. The depth penalty is domain-shaped.** From each target's best n to n=5: PROSE loses 18–33 %,
CODE 7–12 %, STRUCT 1–11 %. Structured output tolerates deep drafting because acceptance holds;
prose does not.

## Practical recommendation

| workload | setting |
|---|---|
| chat / prose | **n=1** |
| code | n=1 (IQ4_XS) or n=4 (IQ2_M) |
| JSON / tool calls | **n=2** (IQ4_XS) or n=4 (IQ2_M) |

The spread is real but modest — 8–11 % between best and worst *sensible* choice. The large
penalty is only at n≥5.

## Scope

One node, one model family, one prompt per domain, `-np 1`, best-of-3, no repeats across
sessions. n≥6 not sampled here (the matrix covers 5 and 7). Finding 4 needs source confirmation
before it is filed as a bug.
