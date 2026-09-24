# MTP on multi-turn agents: inconclusive, leaning toward harm. -5.8 pp, not significant, and not equivalent either

**2026-09-23/24**, RX 9070 XT, buun `38ada0e1b`, `Qwen3.8-27B-UD-IQ3_XXS` (stock unsloth, native
MTP head), argus corpus `families_v4.json` (40 items), bwrap-sandboxed Hermes agent, 6 arms =
MTP off/on x seeds 1-3, alternating, 240 rows, **0 timeouts, 0 infra voids, 0 tool-call leaks**.
Prereg: `PREREG_MTP_AGENTIC.md` + Amendment 1 (timeouts). Scorer: `analyze_mtp_agentic.py`
(committed before the run). Raw rows and events: `raw/` (with `/home/mark` redacted to `~`).
Reproduce: `analyze_mtp_agentic.py data/receipts/mtp-agentic/raw`.

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
