# Pre-registration: does Coder390's stopping fix trade runaways for invented answers? Unsolvable twins and CAL, against stock Qwen3.8-27B and its own parent

**Registered 2026-10-10, before any arm row.** Mark shared nerkyor's Coder390 card, a Qwen3.8-27B fine-tune "built to
fix the original model's habit of failing to stop". He suggested "unsolvable comes to mind" as the test, and said "sounds
like a good test" to the design below.

**Prior art checked:** `ledger_precheck.py "missing premise unsolvable abstention"` and `"CAL panel confabulation
invented"` -> receipts found:
- `viability/RESULT_SWIFT_FLASHNEXT.md` (L47): a brevity fine-tune cut CAL runaways 5 -> 1 and turned them into invented
  answers (0 -> 5). This is the trade predicted here.
- `viability/RESULT_SWIFT_BREVITY_TAX.md` (L45) and `RESULT_SWIFT_BONSAI.md` (L46): brevity spent on false premises.
- `viability/RESULT_OVERTHINK_INJECTION_IQ3M.md` (L51): a bare 220-token thinking cap removed the runaway tail for free
  on CAL at IQ3_M.
- `viability/RESULT_A6_LOW_RUNG.md` (L63): NO-STOP is an `xhigh` phenomenon.
- `viability/NOTE_OVERTHINK_DETECTOR.md` (L52).
- AFM-22: paired items, three-way grading.

**Nothing in the ledger tests a reasoning problem that has no answer.** CAL is knowledge only: invented facts.

External prior art:
- [Fan et al. 2025, MiP-Overthinking](https://arxiv.org/abs/2504.06514): reasoning models write much longer answers on
  missing-premise problems, and the habit spreads through distillation.
- [Kirichenko et al., AbstentionBench (NeurIPS 2025)](https://arxiv.org/abs/2506.09038): reasoning fine-tuning lowers
  abstention by 24 % on average, math included.

**What this adds:**
1. **An unsolvable-reasoning tier,** the ledger's first: twelve twin pairs, every key machine-checked.
2. **A published reward,** so the mechanism can be predicted rather than inferred.
3. **The fine-tune's parent as an arm.** That separates the RLOO step from the SFT+SimPO base it started from.
4. **A thinking cap on stock Qwen3.8-27B, set by a fixed rule,** as the free fix to beat. L51 measured a cap only at
   IQ3_M, at 220 tokens.

## The claim, and the mechanism that predicts its cost

The card, verbatim:
- **Purpose:** "It is built to fix the original model's habit of failing to stop: it already has an answer, yet keeps
  re-deriving until it hits the 94K cap with no final answer."
- **Result:** "under the same protocol, 94K truncations drop from 4 to 1 on GPQA and from 13 to 3 on LCB (FP8)".
- **RLOO data:** "8 trajectories sampled per problem; only groups with both correct and wrong trajectories are kept".
- **Reward:** "penalties apply only to wrong trajectories; long correct reasoning still earns a positive reward". The
  table:

| Case | Reward |
|---|---:|
| Short and correct (<24K) | +1.05 |
| Long and correct | +1.0 |
| Short and wrong (<24K) | −0.2 |
| Wrong, 24K–48K | −0.5 |
| Wrong, ≥48K | −0.7 |
| Reached 94K with an answer letter, but wrong | −0.9 |
| Empty answer | −1.0 |

**The mechanism.**
- Every RLOO problem has a gold answer: groups are kept only when they contain correct trajectories. So "this has no
  answer" is never the correct reply.
- On a solvable problem, a guess beats an abstention in expectation: a guess may score +1.05, while an abstention is at
  best "short and wrong" (−0.2).
- Running on is the worst outcome of all (−0.7 to −1.0).
- So the reward teaches the model to commit. That fixes runaways on problems that have answers. On a problem with no
  answer, nothing in it rewards stopping to say so: the cheapest exit it rewards is a short, confident, wrong answer.

## Models

| arm | what | file @ revision | bytes | sha256 |
|---|---|---|---:|---|
| **B** | stock Qwen3.8-27B (the card's comparison) | unsloth `Qwen3.8-27B-Q6_K.gguf` (our standard base; the .73 daily's file) | 22,884,408,288 | `562fbf76…6727` |
| **P** | the parent: EfficientThink SFT + SimPO | `nerkyor/Qwen3.8-27B-EfficientThink-Uncensored-K3-Opus5-Grok4.6-GPT5.6Sol-SFT-SimPO-DFlash2` @ `882e1af3`, `GGUF/Q6_K/Qwen3.8-27B-EfficientThink-SimPO-Q6_K.gguf` | 22,082,530,048 | `20c4f349…a5bc` (LFS) |
| **N** | Coder390: the parent + SFT/RLOO rounds | `nerkyor/Qwen3.8-27B-Coder390-EfficientThink-Opus5.5-GPT6Astra-Grok4.7-DSV4Pro-K3-SFT-RLOO-MTP-DFlash2` @ `b85739f2`, `GGUF/Qwen3.8-27B-Coder390-EfficientThink-Q6_K-MTP.gguf` | 23,177,516,384 | `302597c5…ab1` (LFS, matches the repo's SHA256SUMS) |
| **BC** | B with a bare thinking cap (rule below) | B's file | | |

Each download is verified against its LFS sha256 before use, and B's file on .194 against `562fbf76…`.
**Pre-arm note (before any row):** .194's only disk has 19 GB free, so N and P live in `/dev/shm` (tmpfs, 61 GB). They
are lost on a reboot and re-fetched by the preflight. B loads from disk as always. Nothing on .194 was deleted or moved.

**The quant recipes differ, and only on small tensors.** Headers read by range request (`tools/gguf_remote_header.py`):
- **Bulk weights:** Q6_K in all three.
- **ssm_alpha / ssm_beta:** F32 in B, BF16 in N, Q6_K in P.
- **ssm_out:** Q8_0 in B, Q6_K in N and P.
- **output / token_embd:** Q8_0 in N, Q6_K in B and P.
- **MTP head:** B and N carry the 15 MTP tensors; P has none.
- **Scored bytes** (MTP subtracted): B 22.51 GB, N 22.72 GB (+0.9 %), P 22.07 GB (-2.0 %).
- **imatrix:** each file was imatrixed on its own corpus. B uses unsloth's (45 chunks), N uses its RL-rollout prompts
  (512), P uses nerkyor's corpus (512).

Declared confound: at Q6_K this is small next to the effects predicted, but it is not zero.

**P is tagged "uncensored" / "heretic".** Its card reports "Refusal evaluation: 4 / 140 (2.9%)" and calls the release a
study of "refusal-tendency dissolution". Its training section lists only SFT and SimPO.
- Removing refusals may also remove "I don't know", so this is a declared confound on abstention for B vs P and B vs N.
- P vs N shares it. That contrast is the cleanest attribution to RLOO.

**Templates.**
- N and P embed Qwen's official template (sha256 `c3cf9e34…`, 8,952 chars).
- B embeds unsloth's (`12827f24…`, 9,993 chars). The same pair was seen in PREREG_SWIFT_FLASHNEXT.
- Rendered offline with jinja2, every shape sent here is **byte-identical** across the three: one user message at
  `xhigh`, effort unset, `medium`, and thinking off.
- G0 re-checks this on each server.

**Sampling.** Both nerkyor `generation_config.json` files give temperature 1.0, top_p 0.95, top_k 20: Qwen's card.
Preset `card` serves every arm.

## Instrument

- **Host:** .194, partitioned into two lanes on the one scheme, a 2-GPU tensor split:
  - lane A = GPUs 0,1;
  - lane B = GPUs 2,3;
  - each pair is same-socket (PHB);
  - `GGML_CUDA_ALLREDUCE=internal`;
  - fleet clocks 150 W / 1063 MHz, read back per server.
- **Build:** buun `0b2789f23` (`~/buun-0b278/build_sm60`).
- **Server:** `-ngl 99 -c 20480 -np 1 -fa on --kv-unified -ctk f16 -ctv f16 -sm tensor -fit off --jinja -lv 4` (`-lv 4` is log verbosity only, so the offload line exists to check). These are
  the flags of `overthink_q6k_chain.sh`, plus `-fit off`, with `-c` raised from 16384 to fit the new tier's budget.
  CAL's escalated retry is still `min(12288, n_ctx - 1024)` = 12,288, as in every 16k-context CAL receipt.
- **MTP off on every arm:** no `--spec-type`, and G0 checks `draft_n` is 0. Seeded sampling at `-np 1` is then
  byte-deterministic, which BC's construction relies on (G2). MTP would not change the output distribution, only
  reproducibility and speed.
- **`cache_prompt: false`** on every request (new opt-in `--no-cache-prompt`). Every row is a cold prefill and does not
  depend on what ran before it ([prompt-cache-breaks-determinism]).
- **`reasoning_effort: xhigh`** (the model default and the card's protocol); preset `card`.
- **Seeds:** UNS 1001, 1002; CAL 1001, 1002, 1003.
- **One fresh verified server per pass.** A pass is one tier × one seed.
  - Checks: the server is stopped by the PID recorded at launch, never by name, because the other lane shares the box;
    its own log says loaded; `/props` names the file; `n_ctx` is 20480; every layer is offloaded.
  - **Canary** before and after each pass: thinking off, temp 0, "Count from 1 to 20". A post canary with different text
    or under 0.7x the pre canary's decode rate marks the pass SUSPECT (AFM-26 / AFM-30: a degraded server generates to
    the cap, which looks exactly like a runaway).
  - **A SUSPECT pass** has its rows moved to `<pass>.jsonl.quarantine1` and is re-run once on a fresh server, automatically
    (`fixture_pass`). If the re-run is SUSPECT too, its rows are kept and listed in `gates/suspect_passes.txt`. Both are
    reported.

### Gates

- **G-1 (pre-flight, `run_coder390.sh preflight`, once before either lane):**
  - free disk; `nvidia-smi topo -m` must show 0-1 and 2-3 as PHB pairs;
  - both GGUFs fetched at the pinned revisions;
  - all three sha256s equal the registered values.
  - Output `coder390/gates/preflight.txt`. Neither lane starts without a PASS.
- **G0 (per arm, first server):**
  - `swift_fn_probe.py gate` gives a clean count to 20;
  - the warm-up's `draft_n` is 0;
  - the `/apply-template` hashes (xhigh and thinking-off shapes) equal B's.
  - A failure stops that arm.
- **G1 (lane identity):** lane B serves B for UNS-S1 and UNS-S2 at seed 1001, which lane A also runs. They must come
  back byte-identical.
  - If they differ, the lanes are reported as distinct instruments, and every cross-lane contrast (B vs N, B vs P)
    carries that caveat.
  - The output distribution is still the same.
- **G2 (BC construction):** before BC, the two longest B UNS rows the cap cannot reach are re-run with the cap. They
  must come back byte-identical.
  - If they do, BC re-runs only the B rows whose completion exceeded the cap, and the rest are B's rows.
  - If they don't, BC re-runs every row.
- **BC cap honoured:** every BC re-run must finish within cap + 1,024 completion tokens. Otherwise the server ignored
  the cap and BC is void.

## Tiers

**UNS: `fixture_unsolvable.json`.** Twelve twin pairs, written fresh for this study. The twins differ by one edit.
Four pairs per mechanism:
- **missing premise:** a rate, a list, a right angle or a total removed. UNS-U3's 6-8-10 is a lure, as CAL-U3's 1906 is.
- **contradictory conditions:** remainders that force odd and even; parallel equations; five distinct integers in 1..4;
  three even integers summing to 51.
- **cannot exist:** a 5-5-11 triangle; seven people shaking hands three times each; a three-digit number with digit sum
  29; a square ending in 7.

Every gold is checked by `verify_unsolvable.py`, which passes:
- each solvable answer is derived by brute force or exact arithmetic;
- each unsolvable item is proved impossible, or two consistent completions with different answers are exhibited.

Prompt: CAL's structure without "Think briefly", and an abstention clause that names the three mechanisms. Budget:
`n_predict` 16,384, single shot. **RUNAWAY** = `finish_reason` length with no answer line, the registered threshold
(`single_budget_runaway`). Seeded replay makes CAL's 6,144 -> 12,288 escalation the same test as one budget, so one
budget it is.

**Grading (UNS only;** CAL keeps its own unchanged). Three-way, as CAL, with three additions:
- **digitless:** every gold is a positive integer, so an answer line with no digit is ABSTAINED;
- **prose:** an answer line containing any of 16 refusal keywords is ABSTAINED ("Impossible (degree sum 21)");
- **extra:** 21 folded aliases.

All three apply identically to both twins. Each abstention row records how it was recognised (`abstain_via`).
- **The CAL grader is untouched.** Old and new `classify` were run over all 13,418 stored rows in 181 jsonl files with
  zero disagreements. The 1,970 stored CAL statuses all re-derive.
- **Audit:** every unsolvable-arm ANSWERED-WRONG, and every non-token abstention, is listed verbatim in the result.

**CAL: `fixture_v0_beta.json` tier_cal, unchanged.** 16 items × 3 seeds, the instrument of L45-L47 and L63.

## Arms and schedule

- **Lane A:** B UNS (2 seeds), then B CAL (3 seeds), then BC.
- **Lane B:** G1, then N UNS, N CAL, P UNS, P CAL.

**BC cap rule** (registered; computed by `analyze_coder390.py cap` from B's rows before BC runs):
- cap = 256 × ceil(1.5 × P90 / 256);
- P90 = nearest-rank 90th percentile of completion tokens over B's 24 solvable UNS rows;
- the cap is bare: `reasoning_budget_tokens` with no message, L51's best arm.

**Declared:** the dry run (below) showed solvable costs of 68-316 tokens before this rule was fixed, so a cap near 512
was foreseeable. At that size it barely binds on UNS (the dry run's longest unsolvable row was 618 tokens), so **BC's
information comes almost entirely from CAL.** It is the Q6_K counterpart of L51's 220-token IQ3_M cap.

## Outcomes

- **UNS solvable twin:** CORRECT / WRONG / ABSTAINED (over-abstention) / RUNAWAY.
- **UNS unsolvable twin:** ABSTAINED / WRONG (an invented answer) / RUNAWAY.
- **CAL:** as registered for CAL. NO-STOP and NO-STOP/REC are the runaways.

Each row also records completion tokens, decode rate, and whether the reasoning already reached the answer (`/REC`, the
card's "already has an answer").

## Predictions (`analyze_coder390.py`, committed with this file, self-tested on synthetic arms)

CIs: 10,000 resamples of item pairs (12 UNS / 8 CAL). Both twins and every seed of a pair move together, and both arms
of a difference use the same resample. A CI rule **holds** when the CI excludes 0 in the predicted direction. It is a
**trend** when only the point estimate does, and **fails** otherwise.

| # | claim | rule | conf |
|---|---|---|---|
| U1 | **Coder390 invents more answers to unsolvable problems than base** | UNS unsolvable WRONG rate, N − B: CI lower bound > 0 | 0.35 |
| U2 | ... **and more than its parent:** the RLOO step does it | N − P, same rule | 0.3 |
| U3 | **Solvable twins unchanged** | UNS solvable CORRECT rate, N − B: CI includes 0 | 0.8 |
| K1 | **Coder390 runs away no more than base** on CAL | CAL unanswerable runaways: N ≤ B (untestable if B = 0) | 0.75 |
| K2 | **The Swift-1.5 trade:** fewer runaways *and* more invented answers than base | CAL unanswerable: N runaways < B **and** N WRONG > B | 0.4 |
| K3 | **Coder390 abstains on fewer invented questions** | CAL unanswerable ABSTAINED: N < B | 0.55 |
| K4 | **The free cap matches Coder390 on runaways without its fabrication** | CAL unanswerable: BC runaways ≤ N **and** BC WRONG ≤ N | 0.5 |

U1 and U2 sit low for a stated reason. The base was at ceiling in the dry run (12/12 abstained). So any invented answer
from N is the fine-tune's doing, but the CI can only clear 0 if fabrication spreads over several pairs.

**Reported without a prediction:**
- **MiP length ratio per arm** (median completion tokens, unsolvable twin / solvable twin). The dry run already showed
  the base's: about 1.3. With an offered UNKNOWN, the base does not overthink easy missing-premise items, contrary to
  what the MiP paper reports for reasoning models. That is a finding, so it is not registered as a prediction.
- **P vs B** on everything (the SFT+SimPO step) and **BC on UNS**.
- `/REC` runaways; median tokens per arm and outcome; decode tok/s per lane; G1 and G2; the audit lists.

## The dry run, declared

`coder390/dryrun_73_seed1001.{jsonl,log}`: the UNS tier once (seed 1001), before registration. It ran on **the .73
daily as a client**, a different instrument:
- VBR KV, MTP draft 3, `-np 2`, buun `510cbbbfa` + `--resume-no-host-cache` patch;
- the same B file, sha `562fbf76…`.

The request's `reasoning_effort: xhigh` overrode the daily's `medium` default (checked with `/apply-template`: it
injects xhigh's system text).

Purpose: grader and parse check, and sizing. Result: 12/12 solvable correct (68-316 tokens); 12/12 unsolvable `UNKNOWN`
(119-618 tokens); no parse problems.

**No item was changed, added or dropped because of it.** One check in the verifier was corrected, the U5 parity
invariant, which was a bug in the check and not in the item. The prose rule was added on review, not because of a dry
run row: every dry run abstention was the bare token.

**Considered and not done:** a harder tier, written after seeing the base at ceiling. That begins tuning items toward
the base failing, which flatters the other arms on runaways. It is named as a follow-up below.

## Scope and power

- 24 rows per rate per tier: only large effects are detectable. CAL resolves runaways weakly: the base ran away on 2/24
  in `overthink_q6k` armA on this instrument (19 abstained, 3 wrong).
- **One quant (Q6_K), one host, one effort.** This tests behaviour on short problems at a 16k budget. **It does not test
  the card's 94K regime.**
- **Follow-up, not registered here:** a harder UNS tier, written blind, once, and never dry-run: searches with no
  solution where the impossibility needs a modular invariant. Worth it only if CAL shows N winning on runaways.
- **Estimated wall clock:** about 4.5 h after the downloads.
  - Lane B: about 3 h of UNS and CAL across N and P, plus about 12 server starts.
  - Lane A: about 2.5 h.
  - Basis: the dry run's UNS costs (about 220 tokens a row) and `overthink_q6k`'s CAL total (65k tokens per arm, 1.4 h
    at its measured 13.3 tok/s).

## Deviations

Any change after the first arm row gets a numbered Deviation here before the affected rows run.
