# Commitments Ledger — what I owe, what's owed to me, what's blocked

Built 2026-08-08 from open issues on `TheTom/llama-cpp-turboquant`, Discord threads, and
`TODO.md`. **Verify before acting** — this is a snapshot, and the GitHub state moves.

Distinct from `TODO.md` (research roadmap) and `PENDING_VERIFICATIONS.md` (SMVP protocol).
This file is only about **obligations to other people**.

---

## A. Owed to others — my move

| # | Who | What | State |
|---|---|---|---|
| A1 | **buun** | TCQ **leg 3** margin bench — the third leg he asked for 2026-07-07 | **IN PROGRESS.** tier 2048 DONE (buun wins, t=−4.05); tier 8192 running; 32768 not started |
| A2 | **TheTom** | **#280** HIP `FLASH_ATTN_EXT` aborts instead of skipping (opened 2026-08-08) | **NOT ACKED.** Reported on gfx1100/RDNA3 by jasstrong. My **gfx1201 is the only RDNA4** in the project — a second-architecture datapoint is cheap and directly useful |
| A3 | **TheTom** | **#268** — I offered to port 29 TQ-relevant test lines (DSv4 MLA shapes, large-k) from the deleted branch | **Issue is CLOSED** (resolved by `2293b1da6`). Offer may be moot — *ask him whether the coverage is still wanted* before spending time |
| A4 | **ekryski** | on-demand sm_60 / 4×P100 kernel-correctness receipts for `iron` | Offered 2026-08-08, accepted. No deadline. Pull-based, not a hosted runner |
| A5 | **Akicou** | ask whether the REAP ladder points are **nested** | Never asked. Affects how much weight the per-rung damage curve carries |

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
