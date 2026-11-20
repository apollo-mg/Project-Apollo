# RESULT: thinking-on A/B, seed 2 -- at xhigh effort the base Qwen3.8-27B declares all 7 impossible items impossible (thinking off: 1) and so does the adapter (thinking off: 5); both solve all 3 twins; nothing gamed; greedy thinking replays byte for byte; stripping the earlier reasoning removes the declaration at 6 of 14 deciding steps and adds none

**Prereg:** `PREREG_SEED2.md` (committed before any seed-2 thinking episode). **Run:** 2026-11-19 21:38 to 11-20
05:28 on .194, `run_seed2.sh`, code `269fea46`; log `seed2/seed2.log`. **Records:** `seed2/raw/{BASE,PIA}/` (20
episodes, each with its exact message history), `seed2/probe_{BASE,PIA}.jsonl` (15 probes). **Readout:**
`summarize_seed2.py`, written after the run (the prereg named the measures and rules), output `seed2/summary.txt`.
Settings: xhigh passed explicitly, earlier reasoning replayed, greedy, 16k per step, 49k context, the v1 instrument
and its reminder unchanged.

## Results (7 impossible items and 3 twins per arm; thinking-off figures are the same items from the main run)

| | BASE thinking off | BASE xhigh | PIA thinking off | PIA xhigh |
|---|---|---|---|---|
| declared "impossible", of 7 | 1 | **7** | 5 | **7** |
| of which before any reminder | 0 | 2 | 4 | 4 |
| twins solved, of 3 | 2 (ranges incomplete) | **3** | 3 | 3 |
| rule broken or gamed | 0 | 0 | 0 | 0 |
| lane-hours for the 10 items | 2.3 | 6.0 | 2.7 | 6.5 |

With thinking on, no episode looped (the loop rule never fired), none hit the step cap or the context (largest reply
10,564 tokens, largest prompt 22,417 of 49,152), and every episode ended in the agent's own finish. The only reminders
were the step-20 one: 5 of BASE's 7 impossible episodes and 3 of PIA's reached it, because at xhigh both models first
read every file one call at a time (about 11 steps), and most of those declarations came at step 21, right after it.

## Predictions

| | result |
|---|---|
| S1 PIA declares at most one more than BASE | **holds, at ceiling, so it says nothing**: 7 vs 7. The registered test cannot separate arms that both declare everything |
| S2 no false "impossible" on twins | holds: 0 of 6 |
| S3 nothing gamed | holds: 0 of 20 |

## Replay check

The four episodes repeated from the sizing run (rle twin and K3 shallow, both arms) are **byte-identical**: every tool
call, every reply and every reasoning text, 15 and 21 steps long. Greedy thinking on this stack replays exactly.

## Preserved-reasoning probe

15 deciding steps re-asked. **The control reproduced the recorded action 15 of 15.** At the 14 steps where the agent
declared "impossible", removing every earlier reply's reasoning (nothing else changed) made it do something else at
that step in **6** (it ran the checks again or wrote a file); at no step did stripping produce a declaration that was
not there. The one non-declaring step probed stayed the same.

This is a one-step counterfactual: without its earlier reasoning the agent did not declare at that step; it may well
have declared a step or two later. Split by whether a reminder came before the probed step (exploratory, small
numbers): 4 of the 6 unprompted declarations were lost, 2 of the 8 that followed a reminder. The reminder seems able
to stand in for the preserved reasoning.

## Reading

1. **At xhigh, the base stops being the problem.** Thinking off, the base declared 1 of these 7; at xhigh, 7 of 7, and
   it solved the hard range twin it could not solve thinking off. Its unprompted declarations went from 0 to 2.
2. **What "xhigh" did is a bundle.** It is thinking, plus the sentence the template injects ("validate key
   assumptions, consider plausible alternatives"), plus the replayed reasoning, plus a step-20 reminder that the
   longer episodes now reach. This run cannot say which part moved the base. Mark's hypothesis (11-19) was that the
   injected sentence pays on heavy reasoning; it is one of the candidates.
3. **The adapter's unprompted edge did not vanish.** The sizing run's single item suggested it might; across seven
   items, PIA declared 4 before any reminder at xhigh, BASE 2. Too few to call a difference.
4. **The fair comparison for a user:** thinking off, the adapter declared 5 of 7, 4 of them unprompted, in 2.7
   lane-hours; the base at xhigh declared 7 of 7, 2 unprompted, in 6.0. That is the model card's own claim -- close
   to thinking-level results without the thinking cost -- seen on a test it was not trained for.
5. **Preserved reasoning carries part of the decision.** When the earlier reasoning is replayed, the agent can act
   on a conclusion it reached steps ago; stripped, it often goes back to checking. Clients that drop the reasoning
   (many do) run a different agent from the one the template intends.

## Cost

6.0 and 6.5 lane-hours against 2.3 and 2.7 thinking off: **about 2.5x**, not the 4.5x the sizing run measured,
because the declarations ended episodes around step 20 where thinking-off episodes looped to 30.

## Limits

One seed, 7 impossible items per arm, both arms at ceiling on the primary measure. Greedy, one run per item (here
shown to replay exactly). The probe changes one step only. The adapter was trained with thinking off. Item outcomes
remain sensitive to incidental tool output (`agentic-gaming/REPLAY_GATE_v2.md`).

## What this suggests next (Mark's choice)

Seeds 3 and 4 at these settings would probably show 21 vs 21 at a cost of about a day of .194. Cells that could
explain the jump instead:
- **the sentence alone:** thinking off, with the exact xhigh sentence placed where the template puts it (checked
  byte for byte through `/apply-template`); about 2.5 lane-hours per arm;
- **thinking without the sentence:** thinking on at `medium` (the template injects nothing); about 6 lane-hours per arm;
- **no reminder:** xhigh with the reminder off, to see how many of the step-21 declarations needed it.
