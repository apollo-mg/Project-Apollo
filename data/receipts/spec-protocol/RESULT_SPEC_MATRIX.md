# MTP beats DFlash2 by 2× on Pascal, and DFlash2 does not fit above ~10 GB

**2026-08-24**, `.194`, 2× Tesla P100 (sm_60), **1063 MHz / 150 W pinned**, `-sm tensor -fit off`,
`-c 8192 -np 1`, f16 KV. buun `7d30a7244` (`build_sm60_new`). Per
`SPEC_DECODE_PROTOCOL_v1.md`: same-session baseline per target, 3 reps best-of, drafter
engagement verified from the server log on every arm. Raw `~/spec_matrix.log`, `/tmp/mx_*.log`.

Draft heads: **DFlash2 Q8_0 2.18 GB** (converted here — no published GGUF exists),
**MTP Q4_0 1.37 GB**.

## Result

t/s, best of 3, by prompt domain:

| target | arm | acceptance | PROSE | CODE | STRUCT |
|---|---|---:|---:|---:|---:|
| **IQ2_M** 10.32 GB | off | — | 15.26 | 15.25 | 15.26 |
| | DFlash2 n=3 | 56.6 % | 10.13 | 11.73 | 12.34 |
| | DFlash2 n=5 | 55.2 % | 10.42 | 12.66 | 14.62 |
| | **MTP n=3** | **74.9 %** | **20.40** | **21.20** | **22.83** |
| | MTP n=5 | 59.6 % | 17.37 | 20.19 | 22.69 |
| | MTP n=7 | 48.3 % | 13.31 | 15.79 | 17.83 |
| **IQ4_XS** 14.25 GB | off | — | 17.23 | 17.23 | 17.23 |
| | DFlash2 (all n) | — | **OOM** | OOM | OOM |
| | **MTP n=3** | **82.1 %** | **22.62** | **24.39** | **26.33** |
| **Q4_K_M** 16.46 GB | off | — | 17.09 | 17.08 | 17.08 |
| | DFlash2 (all n) | — | **OOM** | OOM | OOM |
| | **MTP n=3** | **81.5 %** | **21.95** | **24.67** | **25.17** |

## Findings

**1. MTP wins and DFlash2 loses, on identical hardware and prompts.** At IQ2_M n=3, MTP is
**1.34–1.50×** the no-speculation baseline while DFlash2 is **0.66–0.81×**. A ~2× swing between
methods.

**The mechanism is the protocol's own thesis** — gain = acceptance × cost of a rejected draft.
MTP accepted **239 of 319** drafts; DFlash2 accepted **245 of 433**. DFlash2 generated **36 %
more draft tokens for the same accepted count**, and on a 150 W P100 every rejected token is
compute you cannot spare. MTP shares the target's forward pass; DFlash2 runs a separate model
with its own context.

**2. DFlash2 has a hard memory ceiling between 10.32 GB and 14.25 GB of target.** It runs at
IQ2_M and OOMs at IQ4_XS and Q4_K_M — after already failing six ways against Q6_K
(`../dflash2-sm60/RESULT_DFLASH2_FIT.md`). MTP runs on all four targets at 0.81 GB less.

**3. Domain matters, and it was never measured before this protocol.** Acceptance and throughput
rise **PROSE < CODE < STRUCT** in every single arm — the pre-registered prediction, confirmed
21/21. The baselines are flat across domains (15.25–15.26, 17.23 ×3), so this is a speculation
effect, not prompt difficulty. DFlash2 narrows from 0.66× on prose to **0.96×** on struct at
n=5: still a loss, but the break-even is close.

**4. Better targets draft better.** MTP acceptance **74.9 % → 82.1 %** from IQ2_M to IQ4_XS. The
5–6 pp quant sensitivity measured for MTP on prose understates it across domains.

**5. Both methods invert with depth, MTP just later.** Acceptance falls 74.9 → 59.6 → 48.3 % at
n=3/5/7 while mean draft length rises 2.49 → 3.95 → 4.34. Deeper drafting, smaller accepted
fraction, full compute paid per miss.

**6. IQ4_XS is the best target here.** Faster than Q4_K_M (17.23 vs 17.09 off; 26.33 vs 25.17
with MTP) at **2.2 GB less**, and unlike Q4_K_M it leaves room for a DFlash2-sized head.

## The stack, end to end

| configuration | t/s | vs single |
|---|---:|---:|
| single GPU, no split, no spec (`RESULT_SPLIT_X_MTP` `sing_off`) | 8.53 | 1.00× |
| + tensor split | 13.89 | 1.63× |
| + MTP n=3, IQ4_XS, STRUCT | **26.33** | **3.09×** |

## Scope

One node, one model family, `-np 1`, `-c 8192`, f16 KV, one prompt per domain, best-of-3.
**n=1, 2 and 4 were never sampled** — "Pascal peaks at n=3" is an artifact of S2 testing 3/7/15
and this matrix testing 3/5/7. A depth fill-in is running. Nothing here speaks to RDNA4, where
`S2` measured DFlash climbing monotonically to **150.66 t/s at n=15**.
