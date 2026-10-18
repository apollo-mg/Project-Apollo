# Result -- the Jacobian lens does not pass its sanity gate on Granite 4.1 3B (38 % top-1 agreement at the last source layer, gate 80 %), so no hypothesis is scored; descriptively, round 2's LoRA raised "unknown" tokens on invented universities and capitals, not novels, and mostly in the last layers

**Prereg:** `PREREG_JLENS_IDK.md` (`8a308613`, before any readout). **Lens:** `fit_lens.py`, 100 WikiText-103 test
paragraphs (`passages.json`), 3,672 s on the RX 9070 XT, 511 MB (not committed; refit from the script). **Readout:**
`apply_lens.py` -> `raw/lens_{BASE,LORA,LORA2}.jsonl` (8 minutes for 3 x 240 items, J-lens and logit lens).
**Analysis:** `analyze_jlens.py` -> `RESULT_jlens.json`.

## The gate failed

At the last source layer (38 of 40), the lens's top-1 token equals the model's own next token on **38 % of BASE's
items** (LORA 38 %, LORA2 41 %). The registered gate is 80 %. As registered, J1-J4 are not scored and everything below
is descriptive.

**Exploratory diagnostic (after the gate, 30 items each; in this file because it explains the failure):**

| top-1 agreement with the model | layer 36 | layer 38 |
|---|---:|---:|
| chat prompt, last prompt token: J-lens / logit lens | 0.23 / 0.00 | 0.37 / 0.00 |
| plain Wikipedia text, token 60: J-lens / logit lens | 0.23 / 0.33 | 0.60 / 0.50 |

Even on text like the fitting corpus, transporting layer 38 through Granite's final block with the average Jacobian
recovers the model's next token only 60 % of the time. Granite's last block changes the prediction a lot, and the
linearised average does not capture it. At the chat position the J-lens beats the plain logit lens (0.37 vs 0.00), so
the Jacobian adds something, but not enough for the registered gate. Commentators on the paper flagged transfer to models
Anthropic did not train as an open question; this is one concrete case where the off-the-shelf recipe falls short.

## Descriptive only (gate failed)

Median u_rank (best rank of any "unknown"-type token, layers 12-29; 0 = top-1, vocabulary 100,352):

| arm | invented capitals | invented universities | invented novels | invented operas |
|---|---:|---:|---:|---:|
| BASE | 4,162 | 2,283 | 5,857 | 351 |
| LORA (round 1) | 3,717 | 553 | 6,821 | 452 |
| LORA2 (round 2) | 1,482 | **22** | 5,523 | 202 |

- The pattern mirrors round 2's behaviour (refused: universities 23/25, capitals 15/25, novels 3/25): LORA2's
  "unknown" tokens moved up a long way on invented universities, less on capitals, and hardly on novels.
- By layer, LORA2's drop on invented capitals and universities is largest from layer 28 on (median best rank 983 vs
  5,892 for BASE at layer 28, 275 vs 8,014 at 32, 1,421 vs 11,346 at 36), mostly past the middle band the prereg read. If the lens can be trusted there at all, the
  LoRA acts late, near the output, rather than putting "unknown" into the middle-layer workspace.
- BASE: no "unknown"-type token is in the top 50 of the band for any of the 99 invented items it confabulated, and the
  readout does not separate real questions it gets right from wrong (AUROC 0.52). Read literally, base Granite does not
  represent "I don't know" in the middle layers before confabulating; given the gate, that is a weak reading.
- The logit-lens control shows the same direction with smaller changes.

## What this means for the methodology

- **Keep the lens, keep the gate.** The gate did its job: without it, the descriptive table would have read as a clean
  mechanistic confirmation of round 2.
- **Before using a lens on a new model, validate it on that model first** (a top-1 / top-5 / KL agreement curve on
  held-out plain text and on the actual prompt format), and register the gate from that curve. On Granite the final
  block is heavy, so a lens read at the middle band is untested by a last-layer check alone.
- **Next options:** a model with a published, validated lens (Gemma 4 or Qwen variants have community lenses); a 1,000-
  passage lens on Granite (the README says quality saturates near 100, so this is unlikely to fix a last-block problem);
  or a different readout target layer.

## Not established

Everything in the descriptive section. One lens fit, one model, one position, one token set.
