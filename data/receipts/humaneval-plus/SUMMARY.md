# HumanEval+ matched panel — Puzzle-75B (IQ4) vs Laguna-S-2.1 (Q2), thinking ON/OFF

> ## UPDATE 2026-07-26 — temperature confound removed; the effect holds
>
> The original pair moved two variables (ON@t0.7 vs OFF@t0.6). Two independent replications
> ([offlabel#10](https://github.com/TheTom/offlabel/pull/10)) matched temperature and got
> flat-to-negative results, attributing our +2.64 to that confound. **We ran the missing
> cell — OFF at t0.7 — and the attribution does not hold on this stack.**
>
> | arm | temp | pass@1 | flaky | never | WRONG | no-extractable |
> |---|---|---|---|---|---|---|
> | **ON** | 0.7 | **90.85 %** | **11** | 10 | 30 | 11 |
> | **OFF** | **0.7** | **88.01 %** | **30** | 8 | 58 | **0** |
> | OFF | 0.6 | 88.21 % | 24 | 9 | 56 | 0 |
>
> **At matched temperature the gap is +2.84 points, larger than the original +2.64.**
> Paired over the same 164 problems: **ON better on 26, OFF better on 12, 126 tied —
> two-sided sign test p = 0.034.**
>
> **Temperature does almost nothing to the OFF arm.** 88.21 % (t0.6) vs 88.01 % (t0.7) is a
> 0.20-point difference, and paired it is 16 problems vs 14 — a coin flip. Temperature
> cannot account for a 2.6–2.8 point effect because it does not move this arm at all.
>
> **So the cross-stack disagreement is quant, not temperature.** All three runs, temperature
> now controlled in each:
>
> | stack | quant | engine | temps | ON delta |
> |---|---|---|---|---|
> | **ours** | **Q2_K_XL** | poolside llama.cpp | **0.7 / 0.7** | **+2.84** (paired p = 0.034) |
> | @Blackwellboy | NVFP4 | vLLM 0.25.1 | 0.7 / 0.7 | −1.02 |
> | @TheTom | Q4_K_M | poolside llama.cpp | 0.6 / 0.6 | −2.44 |
>
> Ours and @Blackwellboy's now share an **identical temperature point (0.7/0.7)** and differ
> essentially in quantization — a 3.86-point swing across the quant axis.
>
> **Reading: thinking appears to pay at 2-bit and not at 4-bit or above.** Mechanistically
> plausible — aggressive quantization damages single-pass computation, and extra serial
> compute partially compensates; at higher precision the crutch buys nothing. **That is a
> hypothesis consistent with three data points, not a measured mechanism.** It needs a
> single-stack quant ladder (same model, same engine, same temperature, Q2 → Q4 → Q6 → Q8)
> to become a finding. Nobody has run one.
>
> Also confirmed here: `enable_thinking: false` fired **0/492** — a fourth independent
> confirmation, alongside @Defilan's render check, @Blackwellboy's 0/492 and @TheTom's 0/164.
>
> **Flakiness strengthens too:** ON 11 flaky vs OFF 30 at matched temperature (was 11 vs 24),
> now a 2.7× stability advantage.
>
> Raw: `laguna_hep_results_t07_k3_nothink.json`.

**Campaign:** Battle for 64GB · **Date:** 2026-07-25 · **Node:** `.194` quad Tesla P100 (sm_60)
**Clocks:** 150 W / 1063 MHz — fleet default since 2026-07-17 via `p100-efficiency.service`;
**directly verified immediately before the Puzzle launch** (a post-reboot excursion to
1189 MHz / 250 W was caught and waited out). No independent clock reading was captured for
the two Laguna legs.
**Endpoint (all three runs):** `http://10.0.0.194:8091/v1/chat/completions`
**Benchmark:** HumanEval+ (EvalPlus **extended** test suites) — verified, not assumed: the
local `humanevalplus.jsonl` carries 164 problems and **10.7 MB of test code, mean 65 KB per
problem** (base HumanEval is a few asserts, ~1 KB), each with EvalPlus's generated
`inputs = [...]` table and `is_floats` comparator. Full 164 problems, K=3 = 492 samples/run.
**max_tokens:** 16000 for all three runs (harness default; no override in any launcher — verified)

Each model was run at **its own card-recommended sampling**, which is the correct matched
condition for a deployment comparison. It is deliberately *not* a matched-temperature test.

---

## 1. Headline table

| | **Puzzle-75B-A9B-UD-IQ4-XL** | **Laguna-S-2.1-UD-Q2_K_XL** | **Laguna-S-2.1-UD-Q2_K_XL** |
|---|---|---|---|
| thinking | ON (`enable_thinking=true`) | ON (template default) ᶠⁿ¹ | OFF (`enable_thinking=false`) |
| sampling | t1.0 / top_p 0.95 / top_k 40 / min_p 0.05 | t0.7 / top_p 0.95 / top_k 20 | t0.6 / top_p 0.95 / top_k 20 |
| **pass@1 pooled** | **93.90 %** (462/492) | **90.85 %** (447/492) | **88.21 %** (434/492) |
| per-sweep | 95.1 / 93.3 / 93.3 % | 90.9 / 90.2 / 91.5 % | 86.6 / 90.2 / 87.8 % |
| PASS | 462 | 447 | 434 |
| WRONG | 28 | 30 | 56 |
| TRUNCATED (hit 16k cap) | 1 | 10 | 0 |
| NO_ANSWER | 0 | 1 | 0 |
| EXEC_TIMEOUT | 1 | 4 | 2 |
| solved 3/3 | 149 /164 | 143 /164 | 131 /164 |
| never solved | 5 /164 | 10 /164 | 9 /164 |
| **flaky** (1–2 of 3) | **10 /164** | **11 /164** | **24 /164** |
| median out_toks | 542 | 1 945 | 274 |
| p95 out_toks | 1 838 | 10 152 | 734 |
| total out_toks | 366 857 | 1 457 555 | 173 957 |
| wall clock ᶠⁿ² | 36 243 s (10.1 h) | 72 525 s (20.1 h) | 9 119 s (2.5 h) |

ᶠⁿ¹ The t0.7 run predates the harness's `enable_thinking` plumbing, so its metadata has no
thinking flag and no `reasoning_content` lengths. Thinking-ON is an **inference**, not a
direct measurement — supported by: token medians ON > OFF on **164/164 problems**, median
ratio **6.51×**, and **0/492** ON samples at or below the OFF median. Strong, but label it
as inferred wherever it is quoted.

ᶠⁿ² **Wall clock is confounded by the server build — do not quote it as a speed result.**
The two models require different llama.cpp trees, and the trees were run with **opposite
flash-attention settings** (see §7). Wall clock here is "how long this eval leg occupied the
node," which is operationally useful and is *not* a throughput measurement.

---

## 2. The gap is a stopping-rule failure, not an answering failure

Puzzle beats Laguna-ON by **3.05 points**. Almost none of that is wrong answers.

*Invariant, definition-independent:* **Laguna produced no extractable code on 11/492 samples**
(10 truncated at the 16k cap + 1 NO_ANSWER). **Puzzle: 1/492.**

Conditioning on samples that produced code at all, the gap collapses:

| conditioning rule | Puzzle | Laguna-ON | gap |
|---|---|---|---|
| EXEC_TIMEOUT counted as **wrong code** | 29/491 = 5.91 % err | 34/481 = 7.07 % err | **1.16 pt** |
| EXEC_TIMEOUT counted as **non-answer** | 28/490 = 5.71 % err | 30/477 = 6.29 % err | **0.58 pt** |

Either definition gives the same conclusion: **the majority of the headline gap is Laguna
failing to stop generating, not answering incorrectly.**

**Do not over-read this.** It does *not* say the 11 wedged samples would have passed. The
thinking-OFF arm is the counter-evidence: forcing termination moved WRONG from 30 → 56
while removing all 11 non-answers, for a **net loss** of 2.64 points. Wedging concentrates
on hard problems; those problems mostly fail either way.

Which EXEC_TIMEOUT definition is correct is **unresolvable for these runs — but not by
design.** The harness *does* write a full trace (prompt + generated code + reasoning) for the
first non-PASS sample of every problem, into `{prefix}_traces_{tag}/`. Those directories were
written to the session scratchpad under `/tmp`, which **was wiped by a host reboot on
2026-07-25 ~23:35** before they were copied into the repo. The code for the 5 timeout samples
in these two arms (1 Puzzle + 4 Laguna-ON) existed and is now gone. See §6.

---

## 3. Recovery matrix — cross-config difficulty structure

At K=3 resolution:

- Puzzle never-solved (5): **32, 76, 91, 132, 145**
- Laguna-ON never-solved (10): 32, 55, 76, 86, 91, 116, 132, 134, 145, 163
- Laguna-OFF never-solved (9): 32, 83, 91, 102, 127, 130, 132, 145, 163

**Puzzle's never-solved set is a strict subset of Laguna-ON's — zero reversals.** Puzzle
dominates Laguna-ON on the frontier at this benchmark and this resolution. (K=3 resolution,
not a proven capability ordering; a rare-success problem can hide in 3 draws.)

**HumanEval/76 is the case that earns the best-of-modes metric its keep:** Laguna at Q2 with
thinking **OFF** solves it; Puzzle-75B at IQ4 never does across 3 draws. A single-config
report would have recorded /76 as "beyond the Q2 model."

**Fleet ceiling — unsolved by all three configs (4 problems): 32, 91, 132, 145.**
These are the standing candidates for the reasoning-mode re-test protocol; if they survive
every available mode, they are either genuinely beyond the fleet or defective test cases.

---

## 4. Stability

Use the **flaky counts** (over 164 problems), not the per-sweep ± (std over 3 points, too
thin to compare — especially across models).

Thinking OFF more than doubles sampling sensitivity: **24 flaky vs 11 flaky**, and
always-solved drops 143 → 131. Turning thinking off does not just cost accuracy, it makes
the model's output materially less reproducible.

---

## 5. Methodological receipt: why K≥3

An earlier Puzzle run at **temp 0, K=1** scored **95.1 %** (156/164) — self-labelled in its
own log as *"NOT final — hand-adjudicate non-PASS traces,"* and produced by an older harness
revision (different log format, no pathology buckets).

95.1 % is exactly the **top of this K=3 run's sweep range (93.3–95.1 %)**.

A K=1 comparison would have read as *"greedy beats recommended sampling by 1.2 points."*
The defensible reading is that **the two are not distinguishable at this N**, and the harness
revisions differ so the comparison is confounded anyway. This is *not* a claim that greedy
was a lucky draw — greedy decoding is often genuinely slightly better on HumanEval.

---

## 6. Harness backlog (found by this run)

1. **Never let run artifacts live only under `/tmp`.** The harness already writes per-problem
   failure traces (code + reasoning); they were lost to a host reboot before being copied
   into the repo, which is the sole reason §2's EXEC_TIMEOUT ambiguity can't be settled.
   Run outputs must be written to a persistent path, or rsynced out at completion.
   *(Secondary: the trace writer keeps only the **first** non-PASS sample per problem, so
   a problem with mixed failure modes loses the others. Worth storing all non-PASS samples.)*
2. **Record `max_tokens` in the results metadata.** Verified externally here (no launcher
   overrides the 16000 default), but the truncation comparison depends on it and the JSON
   does not carry it.
3. **Record `enable_thinking` unconditionally**, including when unset (see fn1).
4. **Capture the server's full cmdline + binary path into the results metadata at run
   start.** The two Laguna legs' exact server flags are *not recoverable* (see §7) purely
   because nothing wrote them down.
5. Do **not** publish output-tokens ÷ wall-clock as throughput — it includes prompt
   processing, request overhead and sandbox execution between samples. It is an
   end-to-end eval rate, not an inference rate.

---

## 7. Scope limits

- **Quant asymmetry is not controlled.** Puzzle IQ4_XL vs Laguna Q2_K_XL. This is a fair
  *"what fits in 64 GB"* deployment comparison and an unfair *model capability* comparison.
- One benchmark (HumanEval+), K=3, one node.
- **Server build is NOT matched, and flash-attention state differs.** The two models need
  different llama.cpp trees — Laguna requires the poolside build, Puzzle runs the stock
  build. Same node and same endpoint is *not* the same inference stack.

  | | binary | flags |
  |---|---|---|
  | Puzzle t1.0 leg | `~/llama_stock/build_puzzle/bin/llama-server` | **`-fa on`** — observed cmdline: `-ngl 99 -fa on -sm layer -ts 1,1,1,1 -c 32768 -np 1 --port 8091` (note: no `-fit off`) |
  | Laguna t0.7 / t0.6 legs | poolside build (required) | **not recorded — unrecoverable.** Both legs were launched inline before `ab_server.sh` existed (script dated 2026-07-25 14:26; the legs finished 07-24 23:27 and 07-25 01:59). |
  | Laguna stage-1 server (for reference, launched via `ab_server.sh`) | `~/poolside-llama/build/bin/llama-server` | **`-fa off`** — `-c 32768 -np 1 -ngl 99 -sm layer -ts 1,1,1,1 -fit off -fa off --reasoning on --reasoning-format deepseek --jinja` |

  `-fa on/off` perturbs attention numerics, which is a real if minor caveat on a Q2
  head-to-head. Confound of **unknown sign** — it is not established which way it cuts.
  The thinking ON-vs-OFF comparison is unaffected in kind (both Laguna legs, same model,
  same period), but their flags are equally unrecorded.

## Files

| file | what |
|---|---|
| `puzzle_hep_results_t10_k3.json` / `.log` | Puzzle temp-rec run, per-problem |
| `laguna_hep_results_t07_k3.json` / `.log` | Laguna thinking-ON run |
| `laguna_hep_results_t06_k3_nothink.json` / `.log` | Laguna thinking-OFF run |
| `hep_eval.py` | harness, **revision as of 2026-07-25** — not the exact file that ran every leg. The t0.7 leg predates this revision's `enable_thinking` plumbing (see fn1); this session also added the TOOL_CALL bucket, `rc_chars`, and the penalty params. Earlier revisions are **not recoverable** (scratchpad is untracked). The one scoring-affecting change — the TOOL_CALL bucket — cannot touch these results: no leg passed a `tools` array, so no sample can return `finish_reason=tool_calls`, and TOOL_CALL appears zero times across all 1 476 samples. |
