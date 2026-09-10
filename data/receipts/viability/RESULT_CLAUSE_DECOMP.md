# Clause decomposition: the abstention channel was underpowered, but "consider plausible alternatives" is the clause that runs away

**Date:** 2026-09-07 · **Prereg:** `PREREG_CLAUSE_DECOMP.md` + Amendment 1 (interim-peek rule)
**Node:** `.194`, 4× P100 · `llama_stock/build_puzzle` `73a55486c` · `Qwen3.8-27B-Q6_K`
`-ngl 99 -c 8192 -sm layer`, `--tier cal --effort medium --sampling card`, seeds 1001–1003
**Raw:** `clause_{full,validate,alternatives}_rep{1,2,3}.jsonl`, `clause_run.log`

`RESULT_EFFORT_IS_A_PROMPT_EDIT.md` established `reasoning_effort` is injected system text, and
`RESULT_A6_LOW_RUNG.md` measured what it costs. This asks **which clause** does the damage.
All arms run at `--effort medium` (0-char system block) with the text prepended to the **user**
turn instead, carried in a generated fixture copy so `run_fixture.py` is unmodified.

## Result — 24 items per arm (8 items × 3 reps)

| arm | injected | answerable | ABSTAINED | confab | NO-STOP | chars med | chars total |
|---|---|---:|---:|---:|---:|---:|---:|
| **A** control | nothing | 24 | **21** | 3 | 0 | 755 | 21,243 |
| **B** full | the whole 207-char string | 24 | 18 | 3 | **3** | **8,614** | 208,333 |
| **C** validate | *"Please validate key assumptions."* | 23 | 20 | 4 | **0** | 1,017 | 100,229 |
| **D** alternatives | *"Please consider plausible alternatives."* | 22 | 20 | 2 | **2** | 1,070 | 121,364 |
| *REF* `xhigh` | same text, **system block** | 24 | *13* | *6* | *5* | *5,808* | *215,027* |

## The abstention channel is underpowered, exactly as flagged

C and D are **tied at 20/24**, one below the control's 21. At n=24 that is noise. This was
called out in the session before the arms finished — once B landed at 18 rather than the
predicted ≤16, the effect available to split was 3 points, smaller than the sampling spread.
**No clause-level abstention claim is supported by this run.**

## NO-STOP separates the clauses, and it is the one channel with a signal

| arm | NO-STOP |
|---|---:|
| A control | 0 |
| C "validate key assumptions" | **0** |
| D "consider plausible alternatives" | **2** |
| B both clauses (plus the rest) | **3** |

**"Consider plausible alternatives" produces non-termination; "validate key assumptions" does
not.** D also has the weakest answerable arm (22 vs C's 23 and the control's 24).

This is the mechanism `RESULT_SEARCH_ASYMMETRY.md` predicts, at clause resolution. On a
question whose premise is false, *"consider plausible alternatives"* is an instruction to
**generate candidates for something that does not exist** — the search cannot terminate on a
hit, so it runs until the budget ends. *"Validate key assumptions"* points at the premise
instead, which is the operation the item actually rewards, and it produces zero runaways.

Two of the day's threads meet here: the effort ladder showed `xhigh` produces every NO-STOP
(5/24 against `medium`'s 0), and the within-item analysis showed failures think 2–11× longer
than successes. This names the words responsible.

## Position matters, but the text carries most of it

Same 207 characters, system block (`xhigh`) vs user turn (B):

| | abstention | confab | NO-STOP | chars total |
|---|---:|---:|---:|---:|
| system block | 13/24 | 6 | 5 | 215,027 |
| user turn | 18/24 | 3 | 3 | 208,333 |

Verbosity transfers **completely** (208k vs 215k characters — B's *median* of 8,614 is higher
than `xhigh`'s 5,808). Non-termination transfers **mostly** (3 vs 5). Abstention damage
transfers **about half** (18 sits between the control's 21 and `xhigh`'s 13).

So the runaway behaviour is a property of the words wherever they appear; the abstention loss
is partly positional.

**Superadditivity:** B's median (8,614) is more than 8× either clause alone (1,017 / 1,070).
The two clauses together produce far more output than the sum of their parts.

## Prediction scoring

| # | prediction | conf | outcome |
|---|---|---:|---|
| Q1 | B abstention ≤ 16/24 | 0.55 | **MISS** — 18 |
| Q2 | D worse than C on abstention | 0.70 | **MISS on abstention** (tied 20/20); **right on direction** via NO-STOP (2 vs 0) and answerable (22 vs 23) |
| Q3 | C no better than the control | 0.60 | **HIT** — 20 vs 21 |
| Q4 | `CAL-U3` answers `1906` on all 9 runs across B/C/D | 0.85 | **NEAR-HIT** — 7 of 9 `1906`, plus one `1907` and one empty, both in arm D |
| Q5 | no arm produces NO-STOP | 0.40 | **MISS** — B 3, D 2 |

Q5's miss is the result. It was the prediction that the runaways needed the system-block
position; they do not.

Q4's two exceptions are both in arm D — the same instability seen at IQ3 in
`RESULT_AD_QUANT_LADDER.md`, arriving here from a prompt rather than from weight noise.

## Limits

- 8 items × 3 reps. The abstention channel cannot resolve 1–2 point differences and should not
  be quoted. NO-STOP (0 vs 2 vs 3) and verbosity (5–10× spreads) are the readable channels.
- Position is not fully controlled: the clauses were prepended to the user turn because
  `run_fixture.py` sends no system role. B quantifies the positional cost for the full string
  only.
- **Disclosed peek:** arm C's first rep finished in 22 minutes against arm B's ~50, and that
  wall-clock difference was observed before the arms were scored. Verbosity was one of the two
  scored channels, so the read on that channel was not blind. Recorded rather than corrected —
  the direction was already visible in B vs the control.
- One model, one quant, one node, `medium` effort only.
