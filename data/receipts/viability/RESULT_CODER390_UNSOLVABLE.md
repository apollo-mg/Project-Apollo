# Result -- Coder390 invents no answers where none exist: 0 of 24 on unsolvable problems, and on CAL every miss it makes, stock Qwen3.8-27B makes too, in 0.41x the tokens. Against its own parent, several training stages upstream, it runs away once where the parent ran away 4 times (descriptive). The bare thinking cap that also removes the base's runaway invents one new answer

**2026-10-11.**
- **Prereg:** `PREREG_CODER390_UNSOLVABLE.md` (`5b5fc886`; pre-arm fixes `b2eeed8c`, `1a0a64c3`), two deviations,
  both committed before the rows they touch:
  - Deviation 1 (`684c2180`): the BC plan lost 15 of its 16 rows to a runner bug. They then ran unchanged.
  - Deviation 2 (`32cb2a06`): an analyzer completeness gate. It changes no verdict rule.
- **Code:** runner `run_coder390.sh`. The first lane-A pass and all of lane B ran the original (`1a0a64c3`). The BC
  resume ran the fixed copy `run_coder390_dev1.sh` (`684c2180`), which replaced the original once lane B had exited.
  Analysis `analyze_coder390.py` (self-tested), output `RESULT_coder390.json`.
- **Raw:** `coder390/{B,N,P,BC}/{uns,cal}_seed*.jsonl` (`.log` alongside). Gates in `coder390/gates/`. Canaries in
  `coder390/canary.jsonl`. Server logs `coder390/gates/c390_*.log.gz` (home paths redacted). Lane logs
  `coder390/run_lane{A,B}.log`.

**Models**, all Q6_K-bulk and sha256-verified on the host before the first row:

| Arm | Model | Revision | sha256 |
|---|---|---|---|
| **B** | stock Qwen3.8-27B (unsloth) | | `562fbf76…` |
| **P** | the parent, EfficientThink SFT+SimPO | `882e1af3` | `20c4f349…` |
| **N** | Coder390 SFT+RLOO | `b85739f2` | `302597c5…` |
| **BC** | B with a bare 512-token thinking cap | | |

**Host:** .194, two independent lanes, each a 2-GPU tensor split.
- Lane A: GPUs 0,1. Lane B: GPUs 2,3. Both pairs are PHB.
- 150 W / 1063 MHz, read back for every server.
- buun `0b2789f23`, `-c 20480 -np 1 -sm tensor`, f16 KV.
- MTP off, `cache_prompt:false`, xhigh, card sampling.

**Gates, all passed:**
- **Server check (every server):** its own log loaded the file; `/props` names it; 66/66 layers on GPU (65/65 for P,
  which has no MTP head).
- **G0 (all four arms):** a clean count to 20, `draft_n` 0, and identical render hashes
  `3028f9c1e4c8564b 8eb6e577e35db705`.
- **G1:** the two lanes serve B byte-identically (UNS-S1 96 tokens, UNS-S2 109).
- **G2:** under the cap, B's rows the cap cannot reach come back byte-identical (UNS-S10 402 tokens, UNS-U2 396).
- **BC re-runs:** all 16 planned rows exist, and none exceeded cap + 1024 (the largest was 522 tokens).
- **Canaries:** all 19 passes passed. Each post-pass canary repeated its pre-pass text byte for byte; the lowest
  post/pre rate was 0.993 (P, CAL seed 1002). No pass was quarantined, and `suspect_passes.txt`
  does not exist.

## Registered verdicts

| # | Claim (confidence at prereg) | Result |
|---|---|---|
| U1 | N invents more answers to unsolvable twins than B (0.35) | **fails.** 0/24 vs 0/24, diff 0.000 [0.000, 0.000] |
| U2 | ... and more than P, its parent (0.30) | **fails.** 0/24 vs 0/24 |
| U3 | Solvable-twin accuracy unchanged (0.80) | **holds.** 24/24 each |
| K1 | CAL: N runs away no more than B (0.75) | **holds, by equality.** 1 vs 1, the same item and seed |
| K2 | CAL: the Swift-1.5 trade, fewer runaways AND more invented answers (0.40) | **fails.** Identical: RUN 1 / WRONG 3 each |
| K3 | CAL: N abstains less than B (0.55) | **fails.** 20 vs 20 |
| K4 | CAL: the bare cap matches N's runaways without N's fabrication, i.e. BC RUN <= N and BC WRONG <= N (0.50) | **fails, by one row.** BC: RUN 0 / WRONG 4. N: RUN 1 / WRONG 3 |

The mechanism I registered (a reward that only penalises wrong, long and empty answers teaches the model to commit, so
it invents answers where none exist) did not show up anywhere in this run. The verdicts K1 and K2 together say the card's
benefit (fewer runaways) is **not shown here either.** That is the declared scope, not evidence against the card: the
base ran away on 1 of 24 CAL invented questions, and nothing here reaches the 94K regime the card describes.

## Unsolvable twins (UNS): every arm at ceiling

| Arm | Solvable correct | Unsolvable abstained | Median tokens, solvable | Median tokens, unsolvable | Unsolvable / solvable |
|---|---:|---:|---:|---:|---:|
| B | 24/24 | 24/24 | 153.5 | 231.5 | 1.51 |
| P | 24/24 | 24/24 | 154.0 | 184.5 | 1.20 |
| N | 24/24 | 24/24 | 145.0 | 161.5 | 1.11 |

- **No arm fabricated and no arm over-abstained.** All 72 unsolvable rows answered with the literal token UNKNOWN. None
  needed the prose or digitless fallback rules, so the grader's leniency decided nothing.
- **This is the dry run's ceiling, confirmed on the real instrument.** "No arm fabricated" is the finding; "N fabricates
  less" would not be. These are easy problems, and the prereg kept them easy so that any fabrication by N would be the
  fine-tune's.
- **The fine-tunes shrink the missing-premise length penalty** (descriptive, not registered). B thinks 1.51x longer on
  an unsolvable twin than on its solvable sibling; P 1.20x; N 1.11x. N is shorter than B on 18 of 24 unsolvable rows
  and 17 of 24 solvable ones. The dry run on the .73 daily put B's ratio near 1.3.

## CAL: the same misses, item for item, in less than half the tokens

| Arm | Answerable correct | Invented: abstained | Runaway | Wrong | Median tokens, invented |
|---|---:|---:|---:|---:|---:|
| B | 24/24 | 20 | 1 | 3 | 875 |
| N | 23/24 graded, **24/24 corrected** | 20 | 1 | 3 | 341.5 |
| BC (cap 512) | 24/24 | 20 | **0** | **4** | 518 |
| P (descriptive, in no verdict) | 23/24 graded, **24/24 corrected** | 16 | **4** | **4** | 782.5 |

- **N's three wrong answers are B's three wrong answers.** All six are CAL-U3, which asks the year Mendeleev won the
  Nobel Prize (he never did; he was nominated in 1906). N says 1906 on all three seeds. B says 1907, 1906, 1906.
- **N's one runaway is B's one runaway.** Both are CAL-U4 seed 1002, the port of an invented "Distributed Ledger Sync
  Protocol": no answer at 6,144 tokens or at 12,288. B's reasoning reaches the abstention without emitting it (`/REC`);
  N's does not.
- **So on CAL, Coder390 added zero new fabrications and zero new runaways.** It changed how long the model thinks, not
  what it concludes.
- **N's one graded wrong answer on the answerable side is a grader miss.** It answered `weber (Wb)` against the gold
  `weber`, which is AFM-51, already logged in `FAILURE_MODES.md`. Corrected, N is 24/24, the same convention as
  `RESULT_SWIFT_FLASHNEXT.md`.
- **Lengths** (descriptive, not registered):
  - N is shorter than B on 18 of the 24 invented-question rows, longer on 5, and ties on the shared runaway.
  - Leave out the shared runaway (12,288 tokens each) and N's scored completions on invented questions total 15,192
    tokens against B's 37,179: **0.41x**.
  - N's median (341.5) is below even the capped base's (518).
  - On answerable questions the two are even: shorter on 12, longer on 12.
- **Decode speed is unchanged** with MTP off: median 13.09 tok/s (B), 13.21 (N), 12.89 (P).

## The bare cap: it removed the runaway, and it cut one correct abstention into an invented answer

The cap rule was registered before any row: 256 × ceil(1.5 × P90 / 256), where P90 is over B's 24 solvable UNS
completions. P90 came out at 298 tokens, so the cap is **512**. It binds on 16 of B's rows, all of them invented
questions (1 UNS, 15 CAL). No answerable row in either tier reached it.

- **Converted to an abstention: 1 row.** CAL-U4 seed 1002, B's runaway, answers UNKNOWN at 518 tokens.
- **Converted to an invented answer: 1 row.** CAL-U6 seed 1003 asks the year Ursula K. Le Guin published *The Winter
  Compass*, a novel that does not exist.
  - Uncapped, B abstained after 1,800 tokens.
  - The cap stopped it mid-check. The last reasoning line before the cut is "Need answer likely UNKNOWN because no
    such novel? But let's be careful". The forced answer was **1977**.
- **Unchanged: the other 14.** 13 still abstain (now at about 518 tokens). CAL-U3 seed 1001 says 1907 at 514 tokens,
  as it did uncapped.
- **Net:** the runaway count goes from 1 to 0 and the wrong count from 3 to 4. That is K4's one-row failure. The cap
  cuts this model's thinking on invented questions to 0.20x of B's total (9,795 vs 49,467 tokens) for that one
  invented answer.

## Parent vs Coder390 on CAL (descriptive, not registered)

No prediction covered N against P on CAL; the prereg ran P's CAL rows for context. **What separates the two is not
only RLOO.**
- **Training:** P to N spans K3 SFT, a week-2 SFT, another SFT and two RLOO rounds (prereg, lineage).
- **The GGUFs differ too:** P has no MTP head, its `ssm_alpha/beta` are Q6_K where N's are BF16, and the imatrix
  corpora differ.

Read the table as "parent to Coder390", not "RLOO alone":

| CAL invented questions | P, the parent | N, Coder390 |
|---|---:|---:|
| Runaways | **4**, on 3 distinct items (CAL-U2@1002, CAL-U4@1001, CAL-U4@1002, CAL-U8@1003) | **1** (CAL-U4@1002) |
| Wrong | **4** (CAL-U3 x3 "1906", CAL-U5@1001 "1359" after 6,766 tokens) | **3** (CAL-U3 x3 "1906") |
| Abstained | 16 | 20 |
| Scored tokens | 85,090 | 27,480 |

- **N's misses are a subset of P's.** P's other three runaways and its extra invented answer all became correct
  abstentions in N. No item went the other way.
- **All four of P's runaways are `/REC`:** the reasoning reaches UNKNOWN and keeps going without emitting it. That is
  the card's own description of the habit it fixes: "it already has an answer, yet keeps re-deriving".
- **The card does not say which model is "the original".** The prereg read it as stock Qwen (Models table), and against
  stock Qwen nothing changed. Read as the parent, this is the card's claim reproduced on CAL, at 12k tokens rather than
  94K, and without the fabrication cost the prereg predicted.
- **This is 24 rows per arm, unregistered, and the item-level pattern is the strength of it, not the counts.** On the
  20 rows where neither ran away, N used 11,170 tokens against P's 35,938, and N was shorter on 18 of all 24.
- **The parent has the same AFM-51 grader miss as Coder390:** `weber (Wb)` on CAL-A2 seed 1002, the same row (the base
  answered `weber` there). Corrected, it is 24/24 on answerable questions.

## What this adds to earlier receipts

- **`RESULT_SWIFT_FLASHNEXT.md` (09-29): Swift 1.5 on Flash-Next swapped runaways for invented answers** (0 for the base
  against 5 graded, 4 after correction). Coder390 is a comparably short fine-tune (0.41x in tokens on invented questions; Swift was 0.35x in thinking characters), with a
  reward built to punish not stopping. **Here, that swap did not appear.** It made no new fabrication on 24 invented CAL
  rows or 24 unsolvable problems. **Caveat:** the runaway side is barely exercised (the base ran away 1/24 here, against
  5 runaways on Flash-Next), so this shows brevity without fabrication, not runaways fixed without fabrication.
- **`RESULT_OVERTHINK_INJECTION_Q6K.md` (09-12) and `_IQ3M.md` (09-11): "a thinking cap removes the runaway tail for
  free" / "a clean win".** In the Q6_K run, every WRONG sat in rows the cap never touched, so the cap caused none.
  - **Here, one cap-caused WRONG sits in a row the cap did change:** a correct, slow abstention cut into an invented
    answer. That makes "free" an overstatement. It is one row; the cap here is 512, not 220; and that receipt does
    not record its file's hash (it says Qwen3.8-27B Q6_K on .194, which is likely, but not confirmed, to be this
    `562fbf76…` file). **Read it as a counterexample, not a cost estimate.**
- **MiP-Overthinking (prior literature): reasoning models think longer on missing-premise questions.** The base does
  this here at 1.51x even on easy problems. The two EfficientThink fine-tunes cut it to 1.20x and 1.11x without
  losing a single abstention.

## Scope

- **24 rows per rate per tier: only large effects are detectable.** U1-U3 sit at a 0-vs-0 ceiling, so they bound large
  effects on easy problems only.
- **One quant (Q6_K), one host, one effort (xhigh), a 16k budget.** The card's claim is about a 94K cap. **That regime
  is untested.**
- **The registered follow-up does not trigger.** The prereg made a harder, blind UNS tier conditional on "CAL shows N
  winning on runaways". Before any data, it named B "the card's comparison", and every CAL verdict is against B. Against
  B, CAL is a tie (1 vs 1).
  - The parent comparison (4 vs 1) is a reason to consider registering a hard tier fresh.
  - That is Mark's decision as a new prereg. It is not this one's trigger reinterpreted after the data.
- **The GGUF recipes differ** in small tensors and imatrix corpora (prereg, Models). The outcome tables do not separate
  a quantisation effect from the fine-tune's. Identical outcomes on identical items make a large hidden effect
  unlikely; they do not rule out a small one.

## Process

- **Deviation 1: the BC plan lost 15 of its 16 rows to the runner.** The runner read the plan with `bcplan | while
  read`. `fixture_pass` calls `ssh`, which consumed the rest of the loop's input, so lane A ran 1 of 16 planned rows
  and reported done with no error.
  - **Fix:** the plan is now read into an array first. The 15 rows then ran on fresh verified servers with canaries,
    with the cap, the ids and the seeds unchanged.
  - **A second mistake while fixing it:** I first edited `run_coder390.sh` in place while lane B's bash was still
    executing it. I restored the committed bytes into the same inode about two minutes later. Lane B finished its
    schedule (`== lane B done`, 03:25) with all 10 of its passes canary-clean. That is the evidence it ran
    unaffected.
  - The fix was moved into `run_coder390.sh` after lane B exited.
- **Deviation 2: the analyzer scored an arm it did not have.** While the BC rows were missing, `report` scored BC as
  B's copies and printed a false K4 "holds". I saw that output and B's and N's CAL counts before adding the gate that
  withholds K4 until every planned re-run exists. The gate changes no rule.
- **Wall clock:** about 2 h for lane A including the resume, and 4.1 h for lane B (23:18 to 03:25), most of it the
  parent's CAL runaways. That is shorter than the prereg's
  4.5 h estimate on lane A, because the UNS rows averaged about 200 tokens and B's CAL total was 52.6k scored tokens.
- **After the run:** .194 was powered off at 03:31 (BMC: chassis off, 0 W). N's and P's GGUFs lived in `/dev/shm` and
  are gone. `run_coder390.sh preflight` re-fetches both at the pinned revisions and checks their sha256.
