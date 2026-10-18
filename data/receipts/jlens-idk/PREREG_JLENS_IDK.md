# Pre-registration -- is "I don't know" inside Granite before it confabulates? A Jacobian-lens readout of the idk-lora models

**Registered 2026-10-17, while the lens was still fitting and before any readout.**

**Why.** Round 2 of idk-lora (`../idk-lora/RESULT_IDK_LORA2.md`) found that a mixed-phrasing LoRA refuses invented
standalone names (universities 23/25, capitals 15/25) but not invented novels pinned to famous authors (3/25) or invented
operas (1/25), and refuses almost no real questions it gets wrong. Two stories fit: the model never represents "unknown"
on those items, or it does and the representation is overridden before the output (Anthropic's 2025 account: a default
"can't answer" pathway that familiarity switches off). Anthropic's Jacobian lens (Verbalizable Representations Form a
Global Workspace in Language Models, July 2026; `anthropics/jacobian-lens` 581d398) reads which tokens an internal state
is poised to verbalise, at any layer.

**Prior art checked:** `ledger_precheck.py "jacobian lens logit lens hidden state probe abstention"` -> abstention
receipts that read the answer slot or the in-context decision point (`RESULT_INCTX.md`, `RESULT_CALIB.md`,
`viability/RESULT_HATCH_PROBE.md`) and idk-lora; no lens or hidden-state readout anywhere in the repo. **What this adds:** the first lens readout in this repo; tests the round-2 mechanism.

## Lens

- Fitted on Granite 4.1 3B (bf16, RX 9070 XT) with `jlens.fit`, 100 WikiText-103 test paragraphs (>= 100 words,
  seed 20261017, `passages.json`; corpus file sha256 5f1bea06...), 128 tokens each, `dim_batch` 8 (`fit_lens.py`).
- **Applied unchanged to all three arms** (BASE; LORA and LORA2 merged into the bf16 weights with PEFT
  `merge_and_unload`): a base-coordinate readout. The adapters change the Jacobian slightly; that is a caveat, not refit.
- **Sanity gate:** at the last source layer, the lens top-1 must equal the model's own top-1 next token on at least
  80 % of BASE's items; otherwise the readout is reported descriptively and no hypothesis is scored.

## Readout

- **Items:** the 240 M1 questions in round 2's E2 setting (held-out wrapper F4 and reworded question, no refusal
  instruction), exactly as `round2_gen.msgs("F4", ...)` renders them through the chat template.
- **Position:** the last prompt token (`<|end_of_role|>` after `assistant`), the moment before the first answer token.
- **U-set:** the single-token words " unknown", " Unknown", " UNKNOWN", " unsure", " uncertain", " unclear",
  " fictional", " nonexistent", " sorry", " Sorry" (" fictitious" is two tokens and is left out).
- **Score per item (u_rank):** the best (lowest) rank of any U-set token in the J-lens logits over the middle band,
  layers 12-29 of 40 (30-75 % depth; the paper reports coherent workspace content in an intermediate band). 0 = top-1.
  Every layer's ranks are stored. The same score with `use_jacobian=False` (the plain logit lens) is the control.
- **Behaviour** for each arm and item comes from round 2's E2 rows (strict grade).

## Hypotheses (`analyze_jlens.py`, committed with this file; bootstrap 10,000, seed 20261023)

| # | claim | rule | confidence |
|---|---|---|---|
| J1 | **Familiarity: invented items pinned to a famous name look less "unknown" inside** | BASE median u_rank, invented novels minus invented capitals + universities > 0, CI lower > 0 | 0.55 |
| J2 | **The readout tracks behaviour** | in LORA2, refused vs answered invented items: AUROC of -u_rank >= 0.70 | 0.6 |
| J3 | **LORA2 raised "unknown" inside where its refusals rose** | paired median u_rank LORA2 - BASE on invented capitals + universities < 0, CI upper < 0 | 0.6 |
| J4 | **...and less so on invented novels** | that paired drop is smaller (less negative) on novels than on capitals + universities: difference > 0, CI lower > 0 | 0.5 |

Reported without prediction: the fraction of BASE's confabulated invented items with u_rank <= 50 in the band ("present
but overridden"), per-layer median u_rank curves per arm and item type, real items (base-correct vs base-wrong), the
logit-lens control on every comparison, and the top lens tokens at the band's middle layer for a fixed sample of 10 items
per arm (the descriptive view, no claims).

## Stop rules

- Sanity gate above. A token-level readout is evidence, not measurement: any claim beyond J1-J4 is labelled exploratory.
