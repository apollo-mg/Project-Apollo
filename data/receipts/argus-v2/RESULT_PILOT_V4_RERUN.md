# Result — with a correct scorer the flip vanishes, and so does the discordance gain. Both claims withdrawn.

**2026-09-22 00:01-01:53, `.194`.** Identical configuration to the v4 pilot, re-run after the
three scorer fixes (`RESULT_THREE_SCORER_FIXES.md`): fixture timezone pinned, `WRONG` split into
`WRONG-ACTION`/`WRONG-INACTION`, actions de-duplicated by `(action, target)`. Fixtures
regenerated so they carried the timezone; both verified clean and 0 path-dependent at the run
date. `families_v4.json`, 40 items, 1 rep. Raw: `pilot5/pilot5_{A_q6k,B_iq3s}_20260922.jsonl`.

## This supersedes `RESULT_PILOT_V4.md` on two claims

| | v4, broken scorer | **v4 re-run, fixed scorer** |
|---|---:|---:|
| arm A Q6_K | 62.1 % | **72.4 %** |
| arm B AD-IQ3_S | 82.8 % | **75.9 %** |
| discordance | 22.2-27.6 % | **10.3 %** |
| b : c | 1 : 7 | **1 : 2** |
| McNemar one-sided p | 0.035 | **0.5** |

**1. The flipped direction is withdrawn.** A 20-point gap became 3.5 points. The two arms are
indistinguishable at this n, and the earlier `p = 0.035` was measuring a broken scorer.

**2. "Respacing doubled discordance" is withdrawn.** It fell to **10.3 %** — *lower* than the v3
corpus reported. The apparent doubling was scorer artifacts manufacturing disagreement: strict
list equality failed an arm for reaching the right end state in two calls, and a UTC clause
contradicted an agent reasoning in the host timezone. Both produced one-sided false failures,
and one-sided false failures are exactly discordance.

**I over-corrected once already and was still wrong.** `RESULT_PILOT_V4.md` hand-excluded three
defective items and estimated 66.7 % vs 81.5 %. The measured answer is 72.4 % vs 75.9 %. Reading
traces and excluding what looks broken is **not** a substitute for fixing the scorer and
re-running — the exclusions found the items but understated how much they distorted.

## What the respacing DID deliver

Not everything is withdrawn. Against the v3 pilot:

| | v3 | v4 re-run |
|---|---:|---:|
| void rate | 20 % (9/45) | **5 % (2/40)** |
| wall clock | 186 / 155 min | **111 / 98 min** |
| median per item | 201 / 160 s | **111 / 94 s** |

**A 4x drop in voids and a 40 % cut in wall clock stand**, because they do not depend on the
scorer — a void is "the agent never reached the backend", which no verdict rule changes. Cutting
rungs 4-5 removed the items where agents wandered and gave up. That part of
`RESULT_BRACKET_CONCENTRATION.md` survives; the discordance half of it does not.

## Sizing, with the caveat that matters

| corpus | discordance | items/arm at psi=0.70 | scorer |
|---|---:|---:|---|
| v3 | 12.1 % | 386 | **broken** |
| v4 as scored | 27.6 % | 169 | **broken** |
| **v4 re-run** | **10.3 %** | **453** | correct |

**Only the last row is trustworthy, and it is the worst number yet.** The v3 figure is not a fair
comparison either — that run used the same broken scorer, so its 12.1 % is inflated by the same
artifacts and would also fall on a re-run. **Whether respacing helped or hurt discordance is now
unmeasured**, and answering it needs v3 re-run under the fixed scorer, which is ~3 h of hardware
nobody has spent yet.

## The verdict split earns its keep immediately

```
arm A: WRONG-ACTION 8   WRONG-INACTION 0
arm B: WRONG-ACTION 7   WRONG-INACTION 0
```

Both arms fail in exactly one direction — acting when they should ask — and **neither is ever
over-cautious**. That is a cleaner statement of the corpus's finding than any pass rate here, it
required no re-run to obtain once the classes existed, and it makes the "is B just timid?"
question unaskable rather than merely answered.

Gate rungs: A 8/9, B 9/9, so neither arm is failing the trivially-determined setup check.

## What this does NOT establish

- **Three discordant pairs, p = 0.5.** Nothing about Q6_K versus IQ3_S. The instrument cannot
  separate them at n=29, one rep.
- **10.3 % is itself a small-pilot estimate** on 29 scorable pairs, with a wide interval.
- **v3 has not been re-run**, so no clean v3-vs-v4 discordance comparison exists.
- **Quant remains confounded with packager** (`AFM-30`).
- **The two voids are different items** from the v4 run (`f2-lookup-r2`, `f4-unsat-r2` here),
  which is ordinary run-to-run variation at 1 rep, not a pattern.
