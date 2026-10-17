# Pre-registration -- teach a small model to say "I don't know": one logit bias, IBM's certainty adapter, and a self-labelled LoRA on Granite 4.1 3B, scored on M1

**Registered 2026-10-17, before any M1 row of these models and before any training.** The training pool
(`train_pool.jsonl`, `build_train.py`) exists; no model has answered it.

**Why (Mark, 2026-10-17).** The abstention campaign measured what compression does to "I don't know" (NVIDIA's 2-bit
distillation took Bolt from 0.44 to 0.16 refusal of invented items). This asks the maker's question: what is the
least it takes to put it back into a small model, and is a weekend LoRA competitive with a lab's purpose-built tool?
Mark's hypothesis, tested in Stage A: IBM's Granite models are well calibrated (IBM ships calibration tooling, and
may have prioritised it over raw capability).

**Prior art checked:** `ledger_precheck.py "lora fine-tune abstention refuse unknown"` -> no training receipts here;
measurement receipts only: `RESULT_CALIB.md` (one logit bias on the UNKNOWN tokens restores a quantized file's
answer-slot operating point for half the files; forced slot only), `RESULT_INCTX.md` (in free generation the decision
is made in the sentence the model writes, so a slot bias cannot act after it), `RESULT_MAIN.md` (within-template
AUROC of the slot readout moves at most 0.044 across 20 quants: discrimination is a property of the model),
`FAILURE_MODES.md` L472 (every abstention item needs an answerable partner; over-abstention must be measured).
External: IBM `granitelib-core-r1.0` `uncertainty/granite-4.1-3b` (a LoRA that scores the base model's answer 0-9 after
it is written; card cites Shen et al., ICML 2024, "Thermometer"); the R-Tuning recipe (Zhang et al.: label training
questions by whether the model's own answer is right, train refusals on the ones it gets wrong). **What this adds:**
the three approaches on identical weights, on an instrument with invented items the training never saw, a held-out
question type, and a correct-answers-only control.

## Models (all downloads sha256-verified against the Hub; `verify_downloads.py`)

- **G41** `ibm-granite/granite-4.1-3b` (Apache 2.0): the base for every Stage B arm, because IBM's adapter targets it.
- **G42** `ibm-granite/granite-4.2-3b` (Apache 2.0): baseline only (did calibration change between versions?).
- **PHI** `microsoft/Phi-4-mini-instruct` (MIT): baseline only (a non-IBM model of the same size).
- Each converted here (buun-llama-cpp `38ada0e1b` `convert_hf_to_gguf.py`) and quantized to Q8_0; served on the
  RX 9070 XT (buun `build_rocm`), `-ngl 99 -c 4096 -np 1 -ctk f16 -ctv f16` (KV passed explicitly: buun defaults to
  VBR), fresh server per arm, no drafter.

Vendor sampling (Granite: temperature 1.0, top_p 0.95) is not used: M1 is greedy and thinking-off for every arm, as
for every model before. Granite's template renders thinking-off as `<think></think>`; Phi has no thinking mode
(`--no-think-check`). All three vocabularies have " UNKNOWN", " Unknown" and " unknown" as single tokens, so the slot
readout is valid.

## Stage A: baselines on M1

`run_main.py` (slot + generation, `max_tokens` 1024), arms **IDK_B41**, **IDK_B42**, **IDK_BPHI**.

## Stage B: four ways to abstain, all on G41

1. **BIAS (no training).** Answer-first: the thinking-off render plus `Exact Answer:`, greedy continuation (`/completion`,
   `n_predict` 48, stop at newline) with one `logit_bias` b on the three UNKNOWN tokens. b is chosen on the `calib`
   split (772 real items, never trained on) from the grid -4 to +12 in steps of 0.5, maximising Net (below), then
   applied once to M1.
2. **IBM (their adapter, as documented).** The base model's own M1 generations (IDK_B41 rows) are scored by the adapter
   with transformers + PEFT in bf16: messages `[user: the M1 prompt, assistant: the base answer, user: <certainty>]`;
   certainty = sum over the digit tokens d of P(d) x (0.1 d + 0.05), read at the position after `{"score": "` (the
   card's likelihood mapping). Threshold tau chosen on `calib` (base answers + certainty) from 0.05 to 0.95 in steps of
   0.025, maximising Net; below tau the answer becomes UNKNOWN. Its cost is a second pass per question, reported.
3. **LORA (self-labelled).** Labelling: G41 (the IDK_B41 server) answers every pool item with the M1 prompt, greedy,
   thinking off, `max_tokens` 256; graded by the unchanged CAL grader (`run_pilot.grade`) with the item's aliases.
   known = CORRECT; unknown = anything else. On the `train` split only, the larger class is downsampled to the smaller
   (seed 20261017). Targets: known -> the model's own response text; unknown -> `Exact Answer: UNKNOWN`. Chat template
   with thinking off; loss on assistant tokens only. LoRA r 16, alpha 32, dropout 0.05, on q/k/v/o/gate/up/down
   projections; learning rate 1e-4, cosine, 3 % warmup; 2 epochs; effective batch 16; max length 384; bf16; seed
   20261017; transformers + PEFT on the 9070. Converted with `convert_lora_to_gguf.py`, applied with `--lora` to the
   Q8_0 base; M1 by `run_main.py` as arm **IDK_LORA**.
4. **CTRL (control).** The same recipe trained on the known half only (the same items and targets, no UNKNOWN
   targets). It separates "learned when to refuse" from "a LoRA on this data shifted behaviour in general". Arm
   **IDK_CTRL**.

No invented items are trained on, and `opera` is held out entirely (`build_train.py`): M1's invented items and its
opera cell measure transfer.

## Readouts and predictions (`analyze_idk.py`, committed with this file, self-tested on stand-in arms; paired bootstrap 10,000, seed 20261021)

**Net** per M1 item: +1 for a correct answer on E/H or a refusal on U; -1 for a wrong answer on E/H or any answer on U;
0 for a refusal on E/H or no finished answer. Net is the mean over 240 items. The usual four numbers (easy, hard,
invented refused, hard abstained) are reported for every arm.

| # | claim | rule | confidence |
|---|---|---|---|
| P1 | **Mark's hypothesis: Granite is better calibrated than Phi** | U refusal IDK_B41 - IDK_BPHI >= +0.10, CI lower > 0 | 0.5 |
| P2 | **The LoRA helps** | Net LORA - B41 >= +0.10, CI lower > 0 | 0.65 |
| P3 | **Training beats one number** | Net LORA - BIAS > 0, CI lower > 0 | 0.5 |
| P4 | **IBM's tool is at least as good as the weekend LoRA** | Net IBM - LORA >= 0 | 0.5 |
| P5 | **Knowledge is kept** | E+H correct count, LORA >= 0.9 x B41 | 0.6 |
| P6 | **Refusal transfers to the unseen question type** | opera U refusal LORA - B41 >= +0.20 | 0.5 |
| P7 | **The control does not learn to refuse** | U refusal CTRL - B41 <= +0.05 | 0.7 |

Reported without prediction: G42 against G41 on everything; the self-knowledge AUROC of each base arm's slot
P(UNKNOWN) (positives: items it does not get right, including every U; negatives: E/H it answers correctly); the AUROC
of IBM's certainty on the same split; label balance and counts; training time; the IBM second pass's tokens and
seconds; b and tau as fitted.

## Stop rules

- Fewer than 300 items in the smaller label class on `train`: stop and revisit before training (the balance would
  starve one side).
- Any arm with more than 5 % unfinished answers is reported with that caveat and excluded from the predictions.
- A server fault resumes on a fresh server (run_main skips written ids), recorded.

**Deviation 1 (2026-10-17 ~18:45, before any M1 row): conversion toolchain.**
- buun's `convert_hf_to_gguf.py` failed on Phi-4-mini (`Missing ROPE_FACTORS_LONG for MODEL_TENSORS of PHI3`), so PHI
  was converted with llama_cpp_turboquant `c26cbdffc`'s converter. Both Granites were converted with buun's, as
  registered (after installing `sentencepiece`, whose absence crashed buun's vocab fallback before it reached BPE).
- buun's `build_rocm/bin/llama-quantize` is a stale build (`undefined symbol: llama_print_build_info`), so all three
  Q8_0 files were made with llama_cpp_turboquant `build_rocm` `llama-quantize` (f27268914). Q8_0 is a fixed format;
  serving stays on buun `build_rocm` 38ada0e1b. Sizes: G41 3,619,691,200 B, G42 3,892,652,160 B (IBM's own Q8_0 GGUF is
  3.89 GB), PHI 4,084,610,880 B.
