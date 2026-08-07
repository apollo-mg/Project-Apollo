# Pre-registration — RAG arm: can the pruned model use a fact it is handed?

**Logged 2026-08-07, before any RAG inference on either arm.** Commit timestamp is the record.
Probe set built and inspected first (construction is not data); no model has seen it.

## Why this run matters more than its cost

The closed-book result is settled: 25 % expert pruning leaves code intact and collapses factual
recall (`RESULT_differential_knowledge_vs_code.md`), and the facts are demoted rather than deleted
(`RESULT_PHEAL_gold_rank.md` — gold stays top-100 for 95 % of confident errors, ~2 nats below base).

**REAP is sold for agentic and RAG work**, not as a knowledge store. So the deployment-relevant
question is not "did it forget" — we know it did — but **"can it still use a fact supplied in
context?"** That answer decides how the whole campaign should be framed:

- **Recovers** → the damage is closed-book only. The honest headline becomes *"don't use these as
  knowledge stores; they are fine with retrieval"* — a much narrower and more useful claim, and one
  that is fair to Cerebras's actual positioning.
- **Does not recover** → pruning damaged the *use* of knowledge, not just its storage. That is a
  far bigger finding and it contradicts the marketed use case directly.

## Design

Two context conditions plus a harm control, emitted as ordinary `ikp_probes.json` records so
`ikp_run.py` and `ikp_score.py` run **unchanged** — same grader, same refusal rules, same
`NO_ANSWER` accounting as every other leg.

| cond | n | reference block | tests |
|---|---|---|---|
| **C1** | 358 | exactly the correct Q→A entry | extraction |
| **C2** | 358 | correct entry + 3 from other probes, same tier, deterministic order | **selection under interference** |
| **CTRL** | 132 | C2-style block, on probes the pruned arm still got right closed-book | does the scaffold *harm*? |

**Population** = the 358 probes the base arm answered correctly and the pruned arm then lost
(WRONG or REFUSAL). Closed-book accuracy of the pruned arm on this population is **0 % by
construction** — that is the point; any recovery is measured against zero.

Distractors are drawn from the probe set itself, same tier, selected and ordered by a SHA-256 hash
of the probe id. Nothing is authored, no LLM generates context, so the reference material cannot
leak style or be contaminated. Reproducible from `build_rag_probes.py` alone.

Both arms (base and pruned) run all three conditions. Base is the control for task difficulty:
without it, a low pruned C2 is unattributable.

## Predictions (§8)

| id | prediction | confidence |
|---|---|---|
| **P-RAG1** | pruned **C1 ≥ 90 %** — direct extraction is intact | 0.75 |
| **P-RAG2** | pruned **C2** is within **10 pp** of base C2 — selection under interference is *not* differentially damaged | 0.50 |
| **P-RAG3** | pruned **CTRL ≥ 90 %** — the scaffold does not break probes it already answered | 0.80 |

**P-RAG2 is the hinge.** P-RAG1 and P-RAG3 are instrument checks; a failure on either makes P-RAG2
uninterpretable and the arm must be diagnosed before its result is read.

## Stated in advance: the ceiling is expected and is not a null result

C1 is close to string extraction, so **both arms are likely to sit near 100 %**. That is not a
failed experiment — it localises the damage to storage/recall rather than to instruction-following
or context use, which is exactly the claim that matters for deployment. C2 exists because it is the
condition that *can* separate the arms.

What would genuinely surprise: pruned C1 materially below 90 %, i.e. the model fabricating with the
answer in front of it. Given P-HEAL showed the fact is only ~2 nats down, I do not expect that —
which is why observing it would be worth more than the expected outcome.

## Interpretation, fixed before the data

- **C1 high, C2 ≈ base** → damage is closed-book only. Campaign headline narrows accordingly.
- **C1 high, C2 ≪ base** → the fact can be copied but not *selected*. Routing damage extends to
  in-context use, and the agentic/RAG positioning is directly impeached. The most interesting
  outcome and the one the whole design exists to be able to detect.
- **C1 low** → diagnose before interpreting anything; suspect the scaffold, not the model, and
  check CTRL first.

## Configuration, fixed in advance

Identical on both arms; any deviation invalidates the pair.

| field | value |
|---|---|
| harness | `ikp_run.py` unchanged, `--no-think`, `--concurrency 1` |
| scorer | `ikp_score.py` unchanged, `--exclude-source researcher` already applied at build |
| `--max-tokens` | 64 |
| temperature | 0, K=1 |
| server | `-c 4096 -ngl 99 -sm layer -np 1 --jinja`, `.73` 2×P100 @ 1063 MHz / 150 W |
| gate | G-1a `expert_gating_func = sigmoid` asserted from the load log on **both** arms |

Base runs first (it is the model currently resident); pruned follows after a swap. G-5's 2 pp
`no_answer` divergence rule applies — a divergent truncation rate voids the comparison exactly as
it did for IKP thinking-ON.

**K=1.** Per `agent-benchmark-determinism`, temp-0 on this fleet is not reproducible; this is an
existence proof, not a rate. Given the expected ceiling that is acceptable — but a C2 gap inside
~5 pp should not be read as real without replication.
