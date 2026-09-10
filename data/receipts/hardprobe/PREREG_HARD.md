# Pre-registration — hard questions, medium vs xhigh

**2026-08-21, before any arm ran.** `.194` GPUs 2,3, `Qwen3.8-27B-Q6_K`, 131k ctx, card sampling
(temp 1.0 / top_p 0.95 / top_k 20), 2 seeds per cell.

## Why

`RESULT_EFFORT_SWEEP` found effort changes **nothing** on the answerable arm — but that arm
scored **8/8 at every effort**, so it had no headroom to show a difference. **A ceiling cannot
measure a lift.** These are chosen to be hard enough to fail, which is the only condition under
which `xhigh` could justify its 5.85× cost.

## Items — chosen where a 27B classically fails

| id | trap | gold |
|---|---|---|
| H1 | **Monty Fall** — host opens a door *at random*, not knowingly. Memorised Monty Hall says "switch, 2/3"; the correct answer here is that it makes no difference | 50/50, no advantage |
| H2 | **Trivial problem dressed as a famous hard one** — the boat holds all three items | 1 trip |
| H3 | **Character counting** across a novel string (tokenisation-hostile) | 11 |
| H4 | **Altered surgeon riddle** — the twist is removed, so the memorised "it's his mother" is wrong | grandfather / no puzzle |
| H5 | **Precise multi-step arithmetic** with no round numbers | 4,181 |

H1, H2 and H4 are all **memorisation traps**: the famous version is adjacent and its answer is
wrong here. That is the specific failure mode "think harder" ought to fix if it fixes anything.

## Predictions

| # | prediction | conf |
|---|---|---|
| P1 | `medium` fails ≥2 of the 3 memorisation traps (H1/H2/H4) | 0.60 |
| P2 | `xhigh` beats `medium` on the traps — **the first measured benefit of xhigh** | 0.55 |
| P3 | H3 (character counting) fails at BOTH efforts — tokenisation is not a reasoning problem | 0.55 |
| P4 | H5 (arithmetic) succeeds at both | 0.70 |
| P5 | H1 is the single most-failed item | 0.65 |
| P6 | Overall ≥5/10 correct across both arms — i.e. these are hard but not impossible | 0.60 |

**If P2 fails, `xhigh` has now been given its best chance and found no benefit anywhere.**
