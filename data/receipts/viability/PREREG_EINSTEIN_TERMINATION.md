# Pre-registration — does `{REASON:einstein}` terminate, and does a server-side cap fix it?

**Logged 2026-09-12, before any scored generation.** Prompted by donboyle's report on DavidAU's
community page: *"The Einstein reasoning effort during coding agents (at least in vscode) had no
STOP. It would continue to improve endlessly."* He patched it by appending a STOP CONDITION
paragraph to the mode's system text and said himself *"This is not a good fix."*

This closes our own open thread ("einstein-mode behavioural test — never run").

## The text-level diagnosis this is testing

The einstein block is **1,082 characters** (sha256 of the block: `be5e9dfb90189d5e…`, byte-identical
in both template copies we hold). Read as a specification it does not merely *omit* a stop condition —
it **specifies a loop**, four times over:

1. `Draft your first response, then evaluate it and adjust if required.` — no iteration bound.
2. `Compose your thoughts (which should be at least 5000 tokens)` — a floor with no ceiling.
3. `gE: … → Ponder, assess, creative enhance notions → Refined idea => IdeaArray[].size=20 elements,
   else → Interesting? Pass to rand. agent for refinement, else discard.` — a refinement loop whose
   **only terminating branch is "discard"**, gated on "Interesting?".
4. The persona is *defined* as novelty-seeking (`Seek Novel Emergence`, `[CREATIVITY]`,
   `[BURSTINESS]`), so "Interesting?" is answered yes by construction — the loop's exit branch is the
   one the persona is instructed never to take.

**A separate, independent observation:** `[Temperature: 1.25]` and `[TopP: .2]` appear as text inside
the system prompt. They are **inert** — characters the model reads, not sampler settings. Einstein
mode cannot set temperature. This is not tested here; it is true by inspection and is stated so it is
on the record.

## Instrument

| | |
|---|---|
| model | `Qwen3.8-27B-TurboFCFusion-735-882-Here-Uncen-NEO-CODER-MAX-MTP-IQ2_M.gguf` — DavidAU's own weights (`general.finetune = Brainwaves-NM-HERETIC-BR-LOA1`), 12,124,624,416 bytes, sha256 recorded in the receipt |
| template | `templates/twin-turbo/twin_turbo_template_fixed.jinja`, passed with `--chat-template-file`. **The einstein block is unmodified**; our fixes touched the tool-call guard and the `{REASON:}` scanner only, and the block hashes identically in both our copies |
| engine | `buun-aad85/build_rocm/bin/llama-server` on the RX 9070 XT at 330 W |
| server | `-ngl 99 -c 16384 -np 1 -fa on --kv-unified -ctk q8_0 -ctv q8_0 --jinja`, port 8097. **Verified `kv_bpv = 8.5` from `/slots`** — q8_0, not buun's default VBR |
| readiness | a real completion, not `/health` |

**None of the local DavidAU GGUFs embed these modes.** All three ship the stock ~8.95 KB Qwen
template; `{REASON:}` exists only in the separate template files users pass by hand. That is
consistent with mythrime's note that toolcall2 "will be the one put back to re-GGUF."

## Arms — same model, same items, same seeds

| arm | `reasoning_effort` | cap |
|---|---|---|
| **A** | `xhigh` (the template's default) | none |
| **B** | `einstein` | none |
| **C** | `einstein` | `reasoning_budget_tokens = 1024` |

`n_predict = 8192` on every arm. **Non-termination is defined as `finish_reason == "length"`** — the
generation hit the 8,192-token ceiling instead of stopping.

Arms A and B differ in their injected system text, so they diverge from the first token. **Arms B and
C are the same generation until the cap binds** (fixed seed), so the B-vs-C contrast will be reported
with its divergent-cell count, not its row count — the lesson from
`RESULT_OVERTHINK_INJECTION_Q6K.md`.

## Corpus — 4 items, each with an unambiguous done-condition

Chosen so that continuing past completion is a failure rather than a judgement call. Two coding
tasks (donboyle's use case) and two ideation tasks (einstein's stated domain).

| id | task | done-condition |
|---|---|---|
| `E-C1` | parse a duration string like `1h30m` into seconds | one function |
| `E-C2` | CLI that de-duplicates lines preserving order, with `--ignore-case` | one script |
| `E-I1` | three names for a hardware-benchmarking home lab | exactly three |
| `E-I2` | two approaches to detecting model overthinking, one paragraph each | exactly two |

3 reps, seeds 2001–2003. **4 × 3 × 3 = 36 scored generations.**

## Predictions

| id | prediction | conf |
|---|---|---|
| P-E1 | einstein (B) median thinking > xhigh (A) median thinking | 85% |
| P-E2 | einstein thinking reaches the instructed ≥5000 tokens in **fewer than half** of generations — the mode does not obey its own floor | 60% |
| P-E3 | einstein (B) non-termination rate > xhigh (A) | 75% |
| P-E4 | the cap (C) drives non-termination to 0 | 80% |
| P-E5 | arm C still emits a usable final answer in ≥80% of generations — the cap does not cost the deliverable | 70% |
| P-E6 | the runaway is **inside** `<think>`, not a post-answer refinement loop — i.e. a thinking cap is the right lever and a template edit is not required | 65% |
| P-E7 | on the two ideation items, einstein's overrun is larger than on the two coding items | 55% |

**P-E6 is the one that matters to donboyle**, because it decides whether his fix is even aimed at the
right layer. If the loop is post-answer, no thinking cap helps and it is a harness stop-condition
problem.

## Analysis, fixed now

- Non-termination: count of `finish_reason == "length"` per arm; Fisher exact for A vs B and B vs C.
- Thinking length: median and distribution of reasoning tokens per arm.
- The ≥5000-token claim: fraction of einstein generations whose reasoning reaches 5,000 tokens.
- B vs C reported with divergent-cell count, and the injected budget message subtracted from any
  thinking-length comparison (`tools/score_overthink.py` already does this).

## Declared in advance

- **A pilot will be run first** (1–2 generations) to confirm the effect exists and to sanity-check
  throughput. **Pilot data is not scored** and is excluded from every number above.
- **IQ2_M is a 2-bit quant.** A low-bit model may follow an elaborate 1,082-character instruction
  poorly, which would confound "einstein loops" with "this quant cannot follow einstein". If the
  effect appears, the natural control is the same template on base Qwen3.8-27B at IQ4_XS, which
  separates template from tune; that control is **not** part of this registration.
- **Single model, single quant, single card.** Nothing here generalises to donboyle's setup, which is
  a different quant in a VS Code agent harness with its own turn loop.
- **We are not testing spoon mode** (mythrime's question), which injects a different and much larger
  block (+3,989 chars).

---

## Amendment 1 — the pilot invalidated the primary instrument (2026-09-12, before any scored data)

**What the pilot showed.** 4 unscored generations on `IQ2_M` (DavidAU's weights), 2 items × arms A/B:

| item | arm | finish | completion tokens | thinking |
|---|---|---|---|---|
| `E-C1` coding | A `xhigh` | **stop** | 1,949 | 5,608 ch |
| `E-C1` coding | B `einstein` | **stop** | 1,452 | 4,543 ch |
| `E-I1` ideation | A `xhigh` | **stop** | 374 | 1,342 ch |
| `E-I1` ideation | B `einstein` | **stop** | 444 | 1,817 ch |

- **No runaway anywhere.** Every generation terminated on `stop`; none approached the 8,192 ceiling.
- **Einstein produced *less* thinking than xhigh on the coding item** and more on the ideation item.
- **Nothing came near the instructed "at least 5000 tokens".** The largest einstein thinking block was
  1,817 characters — roughly 450 tokens, about an order of magnitude short.
- **Arm B's reasoning on `E-C1` contained zero einstein-persona markers** — no agents, no novelty
  pass, no `IdeaArray`, no Sternberg. It reasoned like the xhigh arm.

**Why this forces a change.** At IQ2_M the instrument cannot separate *"einstein does not loop"* from
*"this 2-bit quant cannot follow a 1,082-character persona instruction"*. That confound was declared
in the original registration; the pilot shows it is live, not hypothetical, so scoring 36 generations
on it would produce an uninterpretable null.

**The change.** The declared control is **promoted to primary**, and both models are now run:

| | model | what it isolates |
|---|---|---|
| **primary** | `unsloth-v3/Qwen3.8-27B-UD-IQ4_XS.gguf` — **base Qwen**, 4-bit, same template | the **template**, at a bit depth that can follow it |
| **secondary** | `TurboFCFusion…IQ2_M` — DavidAU's weights | the tune, at the depth we have |

Server context drops to **`-c 12288`** for the primary so 14.25 GB of weights and the KV cache fit on
a 17.1 GB card; `n_predict` stays 8,192, so the non-termination definition is unchanged.

**What this costs.** The primary now runs **base Qwen weights, not DavidAU's tune**. It therefore
tests whether *the template* causes a runaway, which is the actionable question for a template fix —
and it explicitly does **not** test whether DavidAU's fine-tuning contributes. If the primary shows a
runaway, the follow-up is his weights at a comparable quant, which we do not currently hold.

**Unchanged:** arms, items, reps, seeds, the non-termination definition, all 7 predictions, and the
analysis plan.

**Seen so far, in full:** the four numbers in the table above. No scored generation has been run, and
no arm-C (capped) generation has been run at all.
