# families_v5 validates: the renamed world behaves like the original (90 % twin concordance), and argus now has 83 items

**2026-09-24**, RX 9070 XT, buun `38ada0e1b`, `Qwen3.8-27B-UD-IQ3_XXS`, MTP off, seed 1, prompt cache off,
`argus/run_argus_v5.sh`. Prereg `PREREG_V5_VALIDATION.md` + Deviation 1. Raw: `raw/val_OFF-s1.jsonl` (83 rows),
`raw/val_fix_B-f2-lookup-r5.jsonl` (the re-run item). Home paths are redacted.

## Gates

| gate | result |
|---|---|
| V1 gate rungs, world B >= world A - 1 | A 8/9, B 8/9: **PASS** |
| V2 no world-B-only INFRA/SUSPECT | 2 flagged -> **1 corpus defect (fixed + re-run), 1 genuine agent behaviour** (below) |
| V3 no UTC rollover | finished 19:47 UTC (and the fix at 19:54). **PASS**, by 13 minutes |

## Measurements (with the fixed item)

| | |
|---|---:|
| **twin concordance** (same pass/fail on template and twin) | **36 / 40 = 90 %** (predicted >= 80 %, conf 0.6: **held**) |
| pass rate, world A | 27 / 40 = 67.5 % |
| pass rate, world B twins | 29 / 40 = 72.5 % |
| discordant pairs (A-only / B-only) | 1 / 3, exact McNemar **p = 0.63** |

**Surface invariance holds.** Renaming every person, company, subject and file does not move the pass rate
detectably (predicted +/-10 pp at 0.7: held, +5 pp).

**90 % concordance means twins are highly correlated.** Much of what decides an item is its structure, not its
surface. So **a twin adds far less than an independent item** for detecting an effect. The MTP-harm test must cluster
by template (40 clusters). The practical gain from v5 is a second, largely redundant measurement per template, plus
3 new structures. A really larger effective n still needs new *templates*, weighted toward ask-side items
(INDEX: the discriminating variance lives there).

## V2 findings

1. **`B-f2-lookup-r5`: my translation defect, fixed.**
   - World A asks *"anything from my **landlord**?"*. "Landlord" appears only in a contact name, so answering needs
     a contact lookup (grounding floor 3).
   - My twin asked about *"the **water company**"*. The email subject already says "Water rate change notice",
     which skips the lookup. The agent answered correctly in 2 reads and was flagged SUSPECT against a floor too
     strict for the reworded question.
   - Fixed to *"my **utility provider**"* ("utility" appears only in the contact name). Rebuilt; `verify_families`
     clean (43/43). Re-run: **CORRECT in exactly 3 reads**.
   - Lesson: **an isomorph must preserve which words are searchable, not just which records match.** The builder
     checks decisions and grounding floors, and neither can see that one request word happens to match another
     field.
2. **`B-f2-lookup-r2`: genuine behaviour, stands.** The agent answered correctly, but by running
   `cat .../fake-google/state.json` (reading the world file) instead of the mail tool. SUSPECT is the right verdict.
   AFM-45 class: the sandbox must expose the world directory for the fake CLI to run.

## Deviation 1 in practice

After the PID-namespace guard change, **5 more host-side listeners** (Mark's Hermes Desktop) were recorded as
`host_new_listeners_unrelated` instead of stopping the arm. The guard change was necessary, not cosmetic.

## Not established

One seed, one model. This validates the instrument; it compares nothing.
