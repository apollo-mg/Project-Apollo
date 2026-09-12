# Result — Swift's brevity is spent in the wrong place, but the confabulation cost is not resolvable here

**Run 2026-09-12 00:43–01:01, RX 9070 XT at 330 W.** Pre-registered in
`PREREG_SWIFT_BREVITY_TAX.md` (`15ecd0c`), logged before the model finished downloading. Raw in
`swift/`, scoring in `swift/score_output.txt`.

**Arms.** SWIFT = `bartowski/ukisai_Swift-Qwen3.8-27b-GGUF` `IQ3_XXS`, 12,320,168,160 bytes,
sha256 `afd35e41…c8c3d39d0`, verified. BASE = the already-collected unrestricted arm A from
`RESULT_OVERTHINK_INJECTION_IQ3M.md` (`Qwen3.8-27B.i1-IQ3_M`). 16 CAL items × 3 reps, card sampling
at `xhigh`, seeds 1001–1003, same runner, same card. 48 generations each, 0 errors.

**Integrity:** Swift ships the stock Qwen3.8 template — its rendered prompt ends `<|im_start|>assistant\n<think>\n`,
identical to BASE. No repeat of the Qwopus packaging surprise, so the thinking comparison is valid.

## Result

| | | ABSTAIN | WRONG | NO-STOP | CORRECT | fail | median thinking |
|---|---|---|---|---|---|---|---|
| **SWIFT** | unanswerable | 18 | 6 | 0 | — | 6/24 | **1,692** |
| **BASE** | unanswerable | 20 | 3 | 1 | — | 4/24 | 2,275 |
| **SWIFT** | answerable | — | 1 | 0 | 23 | 1/24 | **425** |
| **BASE** | answerable | — | 1 | 0 | 23 | 1/24 | 355 |

| id | prediction | result |
|---|---|---|
| P-S1 | SWIFT confabulates more than BASE | **CONFIRMED in direction only** — 6/24 vs 4/24, Fisher **p = 0.724** |
| P-S2 | SWIFT's answerable arm ≥ 21/24 | **CONFIRMED** — 23/24, identical to BASE |
| P-S3 | SWIFT's unanswerable thinking is shorter | **CONFIRMED** — 1,692 vs 2,275 chars |
| P-S4 | No NO-STOP runaway | **CONFIRMED** — 0, against BASE's 1 |
| P-S5 | Thinking is cut more on the unanswerable arm | **CONFIRMED** |

**P-S1 is not a result.** The prereg fixed the bar in advance: an increase to ≥ 12/24 would be
resolvable, smaller shifts would not, *"and the report will say so rather than reading a trend."*
6 vs 4 at p = 0.72 is a trend. It points the predicted way and that is all it does.

## P-S5 is the finding: the brevity is spent backwards

| arm | BASE | SWIFT | change |
|---|---|---|---|
| unanswerable | 2,275 chars | 1,692 | **−26%** |
| answerable | 355 chars | 425 | **+20%** |

Swift thinks **less** where a false premise has to be disproved and **more** where an answer exists.
That is the opposite of the allocation you would design, and it is exactly the asymmetry
`RESULT_SEARCH_ASYMMETRY.md` predicts a brevity intervention would produce: proving a negative is
the expensive case, so a blunt reduction takes its biggest bite out of the search that abstention
depends on.

**It also matches Swift's own card without being told to.** Its two worst benchmark rows are AIME
2026 (−4.67) and HMMT (−3.33) — the long-search tasks — while short-answer benchmarks barely move.

## What Swift actually got wrong

| item | SWIFT answers | BASE |
|---|---|---|
| `CAL-U3` (Mendeleev's Nobel) | **1901, 1906, 1915** — three different years | wrong twice, both `1906` |
| `CAL-U4` (a protocol's default port) | 8346, 7051 | also wrong |
| `CAL-U2` (SI unit of "thermal permittivity") | `J/(m³·K)` | **abstained** |

Five of Swift's six failures are on items BASE also failed. Only `CAL-U2` is new — a fabricated unit
for a quantity that does not exist.

`CAL-U3` is worth noting on its own: Q6_K holds `1906` on **9/9** runs, BASE-IQ3_M produced `1906`
twice, and Swift produced three *different* wrong years. The confident false belief degrades into an
unstable one as precision drops — consistent with the low-bit picture in
`RESULT_OVERTHINK_INJECTION_IQ3M.md`, and a reminder that "less confabulation" at low bit depth can
mean "less commitment" rather than "more knowledge".

## What this does not establish

- **No attribution to brevity training.** SWIFT is bartowski `IQ3_XXS`; BASE is mradermacher
  `i1-IQ3_M`. Quant level and packager both differ, as declared in the prereg. Swift's own `IQ3_M`
  is 14.9 GB and does not fit this card beside a 16k context. **A base `IQ3_XXS` control is the
  next step and is not yet run** — until then, P-S5's asymmetry is a property of *this pair*, not
  demonstrated to be a property of Swift's training.
- **The corpus remains easy at 3-bit.** Same floor effect as last night: BASE fails 4/24, so there
  is little room to detect an increase.
- Nothing about DavidAU, Qwopus or ThinkingCap, which are untested here.
- Nothing about Swift's published benchmarks, which were not reproduced.

## The honest summary

Brevity was **free on answerable questions** (23/24 both) and **not free on the unanswerable ones**,
but the cost is too small to call at this n. The reproducible finding is the *allocation*: this
model spends 26% less deliberation on false premises and 20% more on real questions. Whether that
comes from the tune or from the quant is the experiment we have not run yet.
