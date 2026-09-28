# Pre-registration -- Flash-Next Stage B: with thinking on at `xhigh`, does the 2-bit Flash-Next know when to stop?

**Registered 2026-09-28, before any Flash-Next CAL row was generated.** Stage A (`quant-abstention/RESULT_FLASHNEXT.md`)
measured knowledge and abstention with thinking OFF. There Q2 cost Flash-Next nothing against IQ4, and it beat the
27B at 8 bits. Low-bit damage has shown up elsewhere in STOPPING instead (Bonsai kept its knowledge and ran away), so
this stage turns thinking on.

**Prior art checked:** `ledger_precheck.py "runaway NO-STOP thinking stopping CAL xhigh Flash-Next"`. It found the CAL
`xhigh` corpus of work:
- INDEX L46, L47, L58, L294, L384, L570-571;
- the reference below, `RESULT_OVERTHINK_INJECTION_Q6K.md`, whose arm A is the 27B's unrestricted `xhigh` baseline.

**What this adds:** the first model outside the Qwen3.8-27B line on this stopping instrument; the within-model Q2 vs
IQ4 contrast; and a check of Stage A's "2 bits costs nothing" once the model has to reason and stop.

## Instrument (the 27B reference's, except the model)

- **Harness:** `run_fixture_structfix.py --tier cal --effort xhigh --sampling card --seed 1001|1002|1003 --arm A`,
  unchanged. It covers the 16 CAL items (8 answerable, 8 unanswerable twins), its own escalation, `pick_answer` and
  `classify`.
- **Sampling:** card, meaning temp 1.0, top_p 0.95, top_k 20, min_p 0.0, presence 0.0. This is identical to
  Flash-Next's own published thinking-mode card, checked against both the Qwen and unsloth READMEs.
- **Effort:** Flash-Next's template has the same dial as Qwen3.8 (xhigh by default, `high` rewritten to xhigh), and
  `xhigh` injects the same system text ("Please think carefully … validate key assumptions …"), verified by render.
- **Server:** .194, buun `0b2789f23`, `-sm layer -c 16384 -ctk f16 -ctv f16 -np 1 -fit off`. `-c 16384` is the
  reference's context (INDEX L294: context changes NO-STOP counts).
- **Arms:**
  - **FNQ2:** UD-Q2_K_XL, `-ngl 99`.
  - **FNIQ4:** UD-IQ4_XS, `-ngl 44` (Stage A Deviation 2).
- **Server discipline:** one fresh VERIFIED server per arm, as in Stage A after AFM-50: stopped by name; its own log
  says loaded; `/props` names the arm's file; the offload line matches. One warm-up request is discarded.
- **Reference:** `overthink_q6k/armA_rep{1,2,3}.jsonl`, Qwen3.8-27B Q6_K on 2x P100 (`-sm tensor`) at the same flags.
  It scored answerable 24/24; unanswerable 19 ABSTAINED, 3 WRONG, 2 NO-STOP; median reasoning 753 chars.
  **Hardware differs** (2 vs 4 GPUs, tensor vs layer split). Behaviour is compared; speed is not.

## Analysis (`analyze_flashnext_stopping.py`, committed with this file, self-tested on the reference)

Per arm: answerable ANSWERED-CORRECT; unanswerable ABSTAINED, ANSWERED-WRONG and NO-STOP/REC; total NO-STOP;
median reasoning chars.

## Predictions

| # | claim | rule | confidence |
|---|---|---|---|
| B1 | **Q2 does not stop worse than IQ4** | FNQ2 NO-STOP <= FNIQ4 NO-STOP + 2 (of 48) | 0.6 |
| B2 | **Flash-Next Q2 runs away no more than the 27B** | FNQ2 NO-STOP <= 27B Q6_K NO-STOP + 2, i.e. <= 4 | 0.5 |
| B3 | **Stage A's calibration survives thinking** | FNQ2 unanswerable ABSTAINED >= 27B's 19 - 2, i.e. >= 17 of 24 | 0.6 |
| B4 | **Knowledge survives thinking** | FNQ2 answerable CORRECT >= 22 of 24 | 0.8 |

Reported without a prediction: reasoning length against the 27B, per-item NO-STOP, escalation attempts, and
FNIQ4's own numbers.

**Power:** 24 attempts per arm per group; counts this small detect only large differences. Two NO-STOP rows separate
a pass from a fail on B1 and B2 by design; they test for a big stopping failure, not a subtle one.

## Deviations

Any change after the first row gets a numbered Deviation here before the affected rows run.
