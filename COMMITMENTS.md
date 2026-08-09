# Commitments Ledger — what I owe, what's owed to me, what's blocked

Built 2026-08-08 from open issues on `TheTom/llama-cpp-turboquant`, Discord threads, and
`TODO.md`. **Verify before acting** — this is a snapshot, and the GitHub state moves.

Distinct from `TODO.md` (research roadmap) and `PENDING_VERIFICATIONS.md` (SMVP protocol).
This file is only about **obligations to other people**.

---

## A. Owed to others — my move

| # | Who | What | State |
|---|---|---|---|
| A1 | **buun** | TCQ **leg 3** margin bench | **DELIVERED 2026-08-08.** Tiers 2048 + 8192, buun wins 76/120 and 94/120. Tier 32768 **back-burnered — buun's call**: *"13 hours is rough… you don't need to prove it"* |
| A2 | **TheTom** | **#280** HIP `FLASH_ATTN_EXT` aborts instead of skipping | **MEASURED 2026-08-08**, `data/receipts/rdna4-i280/`. Reproduces on gfx1201. Plus a new finding: `supports_op()` **over-claims** on a 48-of-256 slice (`kv=512 AND mask=1 AND nr23!=[1,1]`), and cross-referencing `support` vs `test` ordering **names the aborting case** that #251's print-after-verdict limitation hides. **Not yet posted to the issue** |
| ~~A3~~ | ~~TheTom~~ | ~~#268 test-line port~~ | **ALREADY DONE — PR #269, merged 2026-08-07.** The email to-do was stale. The PR also corrects the "29 lines" figure with measured generated cases (293 on the deleted branch vs **536** on the default branch — the default has 1.8× *more* TQ coverage). Nothing owed |
| A4 | **ekryski** | on-demand sm_60 / 4×P100 kernel-correctness receipts for `iron` | Offered 2026-08-08, accepted. No deadline. Pull-based, not a hosted runner |
| ~~A5~~ | ~~Akicou~~ | ~~are the ladder points nested?~~ | **ASKED AND ANSWERED 2026-08-08.** Each variant is pruned from the original unpruned base, so cascading is excluded. Recorded in `RESULT_REAP_DOSE_RESPONSE.md` Limits, with the one residual assumption (identical saliency ranking across runs) named. Closed |

## B. Owed to others — *their* move, do not re-offer

| # | Who | What | Why it's not mine |
|---|---|---|---|
| B1 | **TheTom** | **#251** K=15 gfx1201 capture-distribution run | Explicitly conditional: *"once a candidate fix (graph-safe temp allocation in `launch_fattn`) exists."* The fix does not exist yet. **Do not re-offer** |
| B2 | **buun** | what caused the determinism bug | **ANSWERED 2026-08-08**: FA scratch shared between contexts/slots (`6d76b27`) + affine tap (`b90873f`). Closed |

## C. Non-technical, with a real clock

| # | What | Consequence |
|---|---|---|
| **C1** | **Binance.US — 2+ years dormant** | **Escheatment.** State unclaimed-property statutes typically fire at 3–5 years. A single login resets it. Highest consequence-per-minute item on this page |
| C2 | YouTube Premium payment method | Service interruption |
| C3 | Sallie Mae Technology Support Engineer (Indianapolis) | Optional. Reads a tier below where the receipts point — see `resume-career-direction` |

## D. Owed to myself — nobody is waiting, but they're the actual goals

| # | What | State |
|---|---|---|
| D1 | **Battle-for-16GB article** | Headline table stands. **Mechanism section now needs a rewrite** — Findings 5+6 of `reasoning_budget_smoke` show Gemma's empties are cap-deaths, not silent closure, and lm-eval never recorded `finish_reason` |
| D2 | `.194` **NVMe** (cheap Gen3, x4 adapter caps at 3.94 GB/s) | Decided, not bought. 34 GB free is the binding constraint on everything |
| D3 | `.194` **DIMMs** — 4×16 GB into the empty channels | Doubles memory bandwidth; local Kingston lot found |
| D4 | 240V PDU (**6-20P input**, metered) | Metered model would answer the idle-Xeon-draw question with a number |
| D5 | Two stale public drafts: `SKILL_FORGE_DRAFT.md`, `legacy_docs/ubuntu_local/profile_readme_draft.md` | Decide: publish or delete |
| D6 | `git push` — 7+ commits unpushed | Receipts only count once they're off the 96%-full drive |

## E. Repo hygiene, no external party

- Delete `backup/pre-purge-20260807` and `refs/original`. **Never `git push --all`.**
- `/mnt/TG_2TB` at 96% — move dormant model families to the Games HDD (855 GB free).
- `TODO.md` leg-3 entry says the blocker is building `llama-server` in `buun_tree`. **Stale** —
  it's built, and the real harness (`probe_router.py`) was in `margin_bench_for_tom/` all along.

---

**Pattern worth noticing:** every A-item is small. None is more than a few hours. What made
them feel like a backlog is that they were spread across Discord, GitHub, an email inbox and
three files, with no single place that said "these five things." That's a tracking problem,
not a capacity problem.
