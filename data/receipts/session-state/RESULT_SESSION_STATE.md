# Result -- a 3B-active memory writer carries a session's facts about as well as Claude Code's own compaction summary at the same length; its lead over the 27B is volume, not selection; the chance gate failed, so this is descriptive

**Prereg:** `PREREG_SESSION_STATE.md` (`ed3ef807`, before any arm was scored; code frozen at `67328fda`, analysis
`2fa436cf`). **Run:** `run_chain_hy.sh`, `run_chain_qw.sh` (2026-10-19 19:19 -> 23:44). **Aggregates:**
`RESULT_session_state.json`. Gold, arm texts and per-item scores contain private session content and stay local
(`~/.local/share/apollo/session_state_eval/`), as registered.

**Setup as run.**
- HY4/HY8: Tencent Hy-Memory-30B-A3B, Q4_K_M imatrix and Q8_0, both sha256-verified against Tencent's listing, on
  .194 with 4x P100 at 150 W, llama.cpp `f74e2fa`, `-sm layer -np 1 -c 32768`, F16 KV, `reasoning_effort: no_think`.
- QW27a/b: Qwen3.8-27B, the .73 daily driver, through the wake proxy with `enable_thinking: false`, under the
  benchmark lock.
- 13 segments, 48 chunks per writer, 139 scored gold items.

## Gates

| gate | outcome |
|---|---|
| G1 chance <= 0.15 for every arm at 1x | **fails**: max 0.223 (INC); HY4 0.216, HY8 0.194, QW27a 0.129, QW27b 0.086, EXT 0.108. **Every comparison below is descriptive only.** |
| G2 HY8 is the same checkpoint as HY4 | **passes**: metadata agrees apart from name, file type and imatrix fields; all 287 F32 tensors are byte-identical |
| G3 HY determinism | **passes**: segment 80 re-run gives identical items (and the dev slice twice gave byte-identical states) |

## Results (share of gold items carried)

| arm | 0.5x | **1x** | 2x | chance at 1x | space used at 1x | items | s / chunk |
|---|---:|---:|---:|---:|---:|---:|---:|
| HY4 Hy-Memory Q4 | 0.604 | **0.784** | 0.835 | 0.216 | 0.57 | 456 | 69 |
| HY8 Hy-Memory Q8 | 0.626 | **0.770** | 0.863 | 0.194 | 0.59 | 407 | 63 |
| INC Claude Code summary | | **0.734** | | 0.223 | 1.00 | | |
| QW27a Qwen3.8-27B | 0.619 | **0.655** | 0.655 | 0.129 | 0.33 | 364 | 164 |
| QW27b (second run) | 0.590 | **0.597** | 0.597 | 0.086 | 0.33 | 368 | 168 |
| EXT newest lines, no model | 0.180 | **0.324** | 0.475 | 0.108 | 0.92 | | |

"Space used" is the rendered text's length as a share of the 1x budget (INC's length, per segment), pooled over all
13 segments. **The pool is misleading:** in the four segments that hold 116 of the 139 items (75, 78, 86, 87) Hy fills
0.90-1.00 of the budget; the low pooled figure comes from small segments with almost no gold. The 27B fills 0.26-0.76
even there, so its 1x and 2x rows are the same text.

Paired differences at 1x (bootstrap over the 139 items, 95 % CI):

| comparison | diff | CI |
|---|---:|---|
| INC - EXT | +0.410 | [+0.317, +0.504] |
| HY4 - EXT / HY8 - EXT | +0.460 / +0.446 | [+0.374, +0.547] / [+0.360, +0.532] |
| QW27a - EXT / QW27b - EXT | +0.331 / +0.273 | [+0.237, +0.424] / [+0.180, +0.367] |
| HY4 - INC | +0.050 | [-0.036, +0.137] |
| HY8 - INC | +0.036 | [-0.058, +0.129] |
| QW27a - INC / QW27b - INC | -0.079 / -0.137 | [-0.180, +0.022] / [-0.237, -0.043] |
| HY4 - QW27a / HY4 - QW27b | +0.129 / +0.187 | [+0.058, +0.201] / [+0.108, +0.266] |
| HY8 - HY4 | -0.014 | [-0.072, +0.043] |

## Predictions (descriptive, because G1 failed)

| # | prediction | outcome |
|---|---|---|
| P1 | INC carries more than EXT | holds: +0.41 |
| P2 | every writer carries more than EXT | holds: +0.27 to +0.46 |
| P3 | best writer within 0.05 of INC, or above | holds: HY4 +0.05 [-0.04, +0.14] |
| P4 | HY4 >= QW27 | holds: +0.13 and +0.19 against the two runs |
| P5 | HY8 and HY4 within 0.05; identical ops on < half of shared prompts; word Jaccard >= 0.5 | partly: recall -0.014 and 0/48 identical hold; Jaccard 0.427 fails |
| P6 | no personal-category content in any writer's output | holds: 0 deny-list hits in HY4, HY8, QW27a, QW27b |

## Reading

- **Hy-Memory keeps up with Claude Code's own summary at the same length.** In the segments that carry the gold it
  fills the summary's length, and there it carries 0.78 of the items against the summary's 0.73: inside the noise.
  Given twice the room it reaches 0.84-0.86.
- **Hy's lead over the 27B is volume, not better selection** (exploratory, below). Hy carries 0.13-0.19 more than
  Qwen3.8-27B on the same transcript slices, but the 27B writes far less text. Cut to the 27B's own length in each
  segment, Hy carries the same share (0.61-0.66 against 0.60-0.66). So the specialist is not a better judge per
  character; it is more generous, and faster: ~65 s per chunk against ~165 s, though on different nodes and settings
  (Hy on .194's 4x P100 at np 1, the 27B on .73's 2x P100 daily with VBR, np 2 and MTP).
- **The two 27B runs differ by 0.06** on identical inputs (the daily's known bistability). That run-to-run spread is
  as large as the gap between Hy and the summary, which is a reason not to read that gap as a ranking.
- **Quant does not matter here, but every token changes.** Q4 and Q8 carry the same share (difference -0.014), yet
  they produced the same ops on 0 of 48 identical prompts and share only 43 % of their words. They write different
  memories of equal quality.
- **Hy never managed an update.** It proposed 15-16 UPDATEs per run and every one named an item id that does not
  exist, so all were dropped; the 27B proposed ~50, and about a third landed. No writer deleted anything. Over a long
  session Hy's state would grow without consolidating, which matters for a live sidecar more than for this
  per-segment test (accepting `12` for `m12` is the obvious fix to try).
- **Verification drops 8-10 % of proposed ops** in every writer: for Hy mostly rules without a quote that matches
  the cited human line (24 of 40 in Q4) plus the bad update ids; for the 27B mostly bad update ids (32 of 35).
- **Privacy.** The writers never carried excluded personal content: it was redacted before they saw it. Claude Code's
  summaries had 25 deny-list hits. Read by hand: 3 sentences in 2 segments carry personal details of the kind the
  standing rules exclude (one quotes such a detail while instructing that it not be stored); 5 are the rules
  themselves naming the categories; 17 are false alarms (email-shaped commit trailers, a username).
- **Post hoc, not registered:** recall minus chance at 1x is HY8 0.58, HY4 0.57, QW27a 0.53, INC 0.51, QW27b 0.51,
  EXT 0.22. The order of the writers and the summary holds; the margins shrink.

## Exploratory (after seeing the results, not registered)

Hy's state rendered at the 27B's actual length in each segment (the same gold, the same scorer):

| budget = each segment's length of | HY4 | HY8 | that 27B run |
|---|---:|---:|---:|
| QW27a | 0.612 (chance 0.180) | 0.655 (0.180) | 0.655 (0.129) |
| QW27b | 0.612 (0.165) | 0.626 (0.165) | 0.597 (0.086) |

At matched length the 0.13-0.19 gap disappears; Hy still matches more of the wrong segment's gold.

## Deviations

1. **Pairing key (after the first `analyze` output, before any reading).** `analyze` paired items on
   (segment, source, id), which is not unique: repeated memory appends and several directives on one line collapsed
   139 items into 113. The key now numbers repeats. Recall figures (from `score`) are unaffected; the paired
   differences above use all 139 items.
2. An interim `score` ran while QW27b was still in progress (its partial directory excluded); no code changed between
   that and the final scoring.

## Not established

- **G1 failed:** the key-token match is loose enough that a text carries ~20 % of another segment's gold. Part of that
  may be real (each segment is scored against the next one's gold, and neighbouring segments share live topics),
  but that explanation is post hoc. A tighter instrument would score against a non-adjacent segment, or with a judge.
- Gold is 73 % commit subjects: it rewards keeping specifics verbatim, which is the sidecar's design goal.
- One session, one author, 139 items; 83 of them in two segments.
- Writers started each segment empty; a live sidecar carries state forward, and Hy's add-only habit is untested there.
- Whether the state helps after a real compaction (the actual use) is not measured here.

## Addendum 1 result -- Recursive Flint (FL8): follows the format, carries less

**Run (2026-10-21 22:39 -> 23:26):** Flint Q8_0 (sha256 verified) on .194 4x P100, upstream llama.cpp `c7fc509`,
`--reasoning-budget 0` (Addendum 1 Deviation 1), the frozen writer `67328fda`. 48 chunks, **58 s per chunk** (Hy
~65, the 27B ~165). G3: segment 80 re-run identical.

| arm | 0.5x | **1x** | 2x | chance at 1x | items | UPDATEs landed | ops dropped |
|---|---:|---:|---:|---:|---:|---:|---:|
| FL8 Flint Q8 | 0.410 | **0.597** | 0.612 | 0.151 | 724 | 13 | 19 % (165 of them uncited) |
| HY4 (registered) | 0.604 | 0.784 | 0.835 | 0.216 | 456 | 0 | 8 % |
| QW27a / QW27b | | 0.655 / 0.597 | | 0.129 / 0.086 | 364 / 368 | ~17 each | 8-10 % |
| INC Claude summary | | 0.734 | | 0.223 | | | |

Paired at 1x: FL8 - HY4 **-0.187 [-0.266, -0.108]**; FL8 - INC -0.137 [-0.237, -0.036]; FL8 - QW27a -0.058
[-0.137, +0.029]; FL8 - QW27b 0.000 [-0.086, +0.086].

| # | prediction | outcome (descriptive: G1 failed for the registered arms) |
|---|---|---|
| F1 | FL8 within 0.05 of HY4 or above | **does not hold**: -0.19 |
| F2 | FL8 lands UPDATEs (Hy landed 0) | **holds**: 13 landed, 10 dropped (unknown ids); it also tried 33 DELETEs, all on unknown ids |
| F3 | at the 27B's length, FL8 carries more than the 27B | **does not hold**: 0.468 vs 0.655 (QW27a length), 0.511 vs 0.597 (QW27b) |
| F4 | no personal-category content | **holds**: 0 deny-list hits |

**Reading.**
- **Flint follows the format and does the bookkeeping:** one fact per item (Hy packed several), and it is the only
  writer besides the 27B that landed updates.
- **But it carries the fewest specifics per character of any writer.** It writes the most items (724) and fills the
  budget in the gold-heavy segments, yet at every matched length it trails Hy and the 27B. Its items are wordier
  ("Mark approved ...") and keep fewer of the numbers, paths and names the gold is made of.
- **It cites badly:** 165 proposed items (19 %) were dropped for citing lines it had not been shown, twice the other
  writers' rate.
- **IFBench-style instruction following is not extraction fidelity.** Its published strength (format compliance)
  shows here; the skill this instrument rewards (keeping exact specifics, citing correctly) does not.
- **Caveat that matters:** Flint ran with thinking OFF, as every arm did, while its published scores average five
  sampled runs with thinking. It may do better as the reasoning model it is; that is a different, slower arm.
