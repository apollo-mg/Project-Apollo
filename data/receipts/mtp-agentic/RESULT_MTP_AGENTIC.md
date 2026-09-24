# MTP on multi-turn agents: inconclusive, leaning toward harm. -5.8 pp, not significant, and not equivalent either

**2026-09-23/24**, RX 9070 XT, buun `38ada0e1b`, `Qwen3.8-27B-UD-IQ3_XXS` (stock unsloth, native
MTP head), argus corpus `families_v4.json` (40 items), bwrap-sandboxed Hermes agent, 6 arms =
MTP off/on x seeds 1-3, alternating, 240 rows, **0 timeouts, 0 infra voids, 0 tool-call leaks**.
Prereg: `PREREG_MTP_AGENTIC.md` + Amendment 1 (timeouts). Scorer: `analyze_mtp_agentic.py`
(committed before the run). Raw rows and events: `raw/` (home-directory paths redacted to `~`).
Reproduce: `analyze_mtp_agentic.py data/receipts/mtp-agentic/raw`.

## CORRECTION (2026-09-24): the agent was told UTC-12 while the world is UTC

The prereg's "calendar pinned" setup (`TZ=Etc/GMT+12 HERMES_TIMEZONE=Etc/GMT+12`) did not do what it
said:
- `driver.py` overrides `TZ` to the world profile's `UTC` when it spawns the agent.
- `HERMES_TIMEZONE` was inherited, and Hermes reads it first
  (`hermes-go/agent/system_prompt.py:809-840`). So the model's system prompt said
  **`Conversation started: Wednesday, September 23, 2026 (Etc/GMT+12, UTC-12:00)`** while every world
  timestamp is UTC.
- It surfaced in the transcripts at least once: *"If you meant 11am in your local time (UTC-12), that
  would be 23:00 UTC..."*.

**What still stands:** both arms of every pair ran under the identical condition, so the paired
MTP-vs-off comparison is valid.

**What does not:**
- Absolute pass rates were taken under a timezone mismatch that no earlier argus run had. Earlier runs
  had `TZ=UTC` and no `HERMES_TIMEZONE`, so Hermes fell back to UTC. Do not compare 75.0 % / 69.2 %
  with other argus receipts.
- The mismatch may have hurt the time-of-day items (f4/f6/f8) in both arms. Whether it *interacts*
  with MTP is untested.

**Fix going forward:** set `HERMES_TIMEZONE` to the world's zone (UTC), never to a pinning zone, and
keep run windows inside one UTC day. Found by review (advisor) while designing families_v5.

## Primary result (judge void rule, unit = item, as registered)

| | MTP off | MTP on |
|---|---:|---:|
| pooled pass rate (120 item-seeds each) | **75.0 %** | **69.2 %** |
| items where MTP scored better / worse | 2 | **7** |

- **mean d = -5.8 pp**, 95 % CI **[-12.2, +0.5]**, exact sign-flip p = **0.12**.
- **Equivalence at ±10 pp: NOT shown.** The 90 % CI [-11.1, -0.6] crosses -10.
- **Harm: NOT shown** at α = .05.

By the prereg's own table this is **inconclusive**. It does not license "MTP is safe for agents",
and it does not license "MTP hurts agents". The registered predictions: equivalence (0.60) **failed**;
harm detected (0.10) **did not occur**.

**Secondary (noise-floor void rule):** -4.4 pp, 90 % CI [-9.7, +0.9], so it *would* pass the ±10 pp
TOST. The primary rule governs. Under that rule the answer is inconclusive, and the rule-dependence
is itself a sign the effect sits right at the margin.

**Timeouts:** none in any arm (item limit 2,400 s; slowest item 185 s in the smoke). The
timeouts-void sensitivity is identical to the primary.

## What the direction looks like (descriptive, not registered)

- **The flips lean one way.** Of 13 item-seed flips into or out of `WRONG-ACTION`, **9 go into it
  under MTP** (from `CORRECT` or `CLARIFIED`) and 4 go out (binomial p ≈ 0.27). The recurring
  pattern is MTP taking an action where MTP-off asked for clarification or held off (f7-recipient-r5 in 2 of 3 seeds,
  f5-conflict-r2 in 2 of 3). **A hypothesis for a follow-up, not a finding.**
- **MTP is less consistent across seeds.** `tools/argus_reps_compare.py` in-run floor, judge rule:
  within-OFF 17.2 %, **within-MTP 23.7 %**, between 18.6 %.
- **That tool's own paired t on 31 items gives p = 0.030 (-8.6 pp).** It is reported so nobody has to
  find it, but it is not the registered test. It filters to a different item set (31 of 40), uses a
  t-test rather than the sign-flip, and choosing it after seeing both would be p-hacking. The
  registered test says p = 0.12.

## Consequence breakdown (post-hoc, 2026-09-24, Mark's framing: "harmful only if it changes the result")

Same item, same seed, MTP vs MTP-off (120 pairs):

| | count | share |
|---|---:|---:|
| identical path and reply | 1 | 0.8 % |
| **different path, same outcome** | **102** | **85.0 %** |
| different failure label, same pass/fail | 2 | 1.7 % |
| outcome **better** under MTP | 4 | 3.3 % |
| outcome **worse** under MTP | **11** | **9.2 %** (9 of them `WRONG-ACTION`) |

- **MTP changes the trajectory in 119 of 120 runs,** but 85 % of those changes are free: the same
  outcome, +0.14 tool calls on average, and a median time change of -0.3 s.
- **Outcome flips are 12.5 %** and run **11:4 against MTP** (binomial p ≈ 0.12, consistent with the
  registered test).
- **Deployment reading:** path differences are irrelevant. Outcome flips are the risk, and they are
  mostly *irreversible wrong actions*, which speed cannot buy back. For retryable, verifiable work, the
  right metric is expected time to success (per-attempt time / success rate), and there MTP's decode
  speed likely wins. That needs the caching-on time-to-completion run.

## What the smoke established

The same seed with MTP off reproduced **byte-identical** replies, tool-call sequences and thinking
lengths on all 3 smoke items (`raw/smoke_*`). So every OFF-vs-MTP difference at a matched seed is
produced by speculation, not by run-to-run noise in the harness.

## What this adds to prior art

`battle16gb/MTP_STRUCTURED_OUTPUT.md` found single-turn tool calls **stable** under MTP (n=6).
Multi-turn is different: MTP changes trajectories often (18.6 % between-arm discordance), and on
this model the changes lean negative, but not beyond what 40 items can resolve. **"Tool calls hold"
does not carry over to "agent outcomes hold"**, which is the claim people actually rely on.

## Deployment reading, stated carefully

MTP gave ~2x decode here (27.6 -> 55.8 t/s on a code prompt; 40.9 vs 27.5 t/s in agent turns).
The outcome cost is somewhere between **+0.5 pp and -12.2 pp** (95 %). For latency-sensitive chat,
keep it. For unattended agents where one wrong action is expensive, there is **no evidence that it
is safe** at the ±10 pp level on this model. The cheap resolution is more items: at this effect size
and spread (per-item SD 0.198), about 90-100 items gives 80 % power to detect -5.8 pp.

## Not established

- One model and quant, one card, one harness, `n-max 2`, card sampling at temp 0.6.
- **Speed in deployment is not measured.** Prompt caching was off (bistability), so per-item time was
  prefill-dominated and says nothing about real MTP gains. A caching-on, time-to-completion run is a
  separate test.
