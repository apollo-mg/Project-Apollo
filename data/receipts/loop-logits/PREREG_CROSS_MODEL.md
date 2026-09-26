# Pre-registration -- cross-model replay: would a healthy Qwen3.8 commit where Bonsai reopened?

**2026-09-26 morning, before any cross-model probe.** Prompted by buun: *"did you run an identical prompt through
something like Q8 to compare?"* Identical *prompts* were already run (marker-penalty Q6_K and IQ3_XXS arms: the
healthy quants also think 13-15k tokens on these items, and Q6_K capped once, but they land on UNKNOWN). This test
feeds Bonsai's **identical token sequences** to a healthy model and reads its next-token distribution at the same
decision points.

**Prior art checked:** `RESULT_LOOP_LOGITS.md` (Bonsai's own replay, this campaign) and
`RESULT_MARKER_PENALTY*.md` (the generations these traces come from).

## Instrument

- **Model:** `.73`'s daily driver, Qwen3.8-27B **Q6_K** (KLD 0.0028 against Q8_0, `exl3-campaign/RESULT_EXL3_KLD.md`),
  buun `0b2789f23`, VBR KV, `-np 4`. It is called directly at `:8080` (the proxy does not forward `/completion`).
  - The model path and build are recorded from `/props` at run time.
  - `-np 4` means these requests share the server with Hermes, so a slot may be displaced. Accepted by Mark.
- **Same input:** the prompt is rendered by `.73`'s own `/apply-template` (xhigh) and tokenized by `.73`. A gate
  **(S)** requires, for every replayed trace, that `.73`'s token ids at every probe position equal the ids Bonsai's
  replay used. Bonsai 2 shares Qwen3.8's tokenizer and renders `xhigh` byte-identically
  (`agentic-ladder/FINDING_BONSAI_TEMPLATE_DEFECT.md`). If S fails for a trace, that trace is dropped and the
  failure reported.
- **Probe:** `/completion`, `cache_prompt: false`, `n_predict 1`, `n_probs 20`, raw probabilities. The points are:
  - all 24 wrap-up points in `EXPLORE_wrapup.json`;
  - the real END point of every terminating trace that has a wrap-up line.

## Predictions

| # | claim | test | conf |
|---|---|---|---:|
| X1 | control: Q6_K reads Bonsai's closing context as closing | at Bonsai's real END points, Q6_K P(`</think>`) >= 0.5 at >= 80 % of them | 0.70 |
| X2 | Bonsai re-checks correct drafts more than a healthy model would | at the 3 points where Bonsai drafted **UNKNOWN** and then re-checked (LONG-OK U2 r2 @7957, SHORT U2 r1 @3982, SHORT U8 r1 @3058), Q6_K P(`</think>`) >= 0.5 at >= 2 of 3 | 0.40 |
| X3 | a healthy model would not commit to the loops' states either | at the 5 loop reopen points, Q6_K P(`</think>`) < 0.5 at >= 4 of 5. The loops' drafts are invented ("1330") or undecided, so re-checking is the *right* move for a healthy model | 0.60 |

**Descriptive:** at each point, Q6_K's top 5 next to Bonsai's top 5. At identical prefixes, does Qwen open its
re-checks with the paper's markers ("Wait", "But") where Bonsai opens with "Double" and "Let"? That is buun's
"model-specific tokens" point, measured directly.

**Reading:**
- **X2 true:** Bonsai's excess re-checking of correct answers is model damage at the commit point.
- **X2 false:** a healthy Qwen3.8 at `xhigh` would also re-check there, so the habit is the effort instruction
  or the prompt, not the quantization.

## Not established by design

- A teacher-forced replay of Bonsai's text into another model. Q6_K is reading Bonsai's words, not its own.
- 3 correct-draft points, so X2 is close to anecdotal.
- One healthy quant (Q6_K), not BF16.

## Amendment 1 (2026-09-26 ~12:40, after the wrap-up-point results, before any mid-loop probe): every 10th boundary inside the loops

The wrap-up-point result (16/16 agreement at the end of wrap-up lines) cannot show whether a healthy model would
**start** wrapping up earlier in the same text, and those points were chosen where the text nearly dictates the
next move. This amendment probes Q6_K at **every 10th newline boundary** of the 3 LOOP traces and of LONG-OK CAL-U2
rep 2 (the reference). The probe is identical to above, and the positions are the ones in `full_*` (Bonsai's
recorded top-20 at the same positions). Output: `raw/xmodel_q6k_every10.jsonl`.

| # | claim | test | conf |
|---|---|---|---:|
| Z1 | mid-loop continuation choices are shared too | top-1 agreement, Q6_K vs Bonsai, over the sampled LOOP boundaries >= 80 % | 0.50 |
| Z2 | a healthy model would have started wrapping up earlier | at >= 3 sampled LOOP boundaries, Q6_K's P("Need") exceeds Bonsai's by >= 0.30 | 0.35 |

**Descriptive:**
- the mean P("Need") of each model;
- a top-20 divergence per boundary (KL over the union of both top-20s, with the missing mass lumped), LOOP vs the
  LONG-OK reference;
- the boundaries where the top-1 tokens differ, with both top-3s.
