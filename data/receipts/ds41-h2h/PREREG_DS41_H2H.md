# Pre-registration -- DeepSeek-V4.1-Flash-1017 at matched bytes: ISTA's GSQ-RCO allocation vs Unsloth's dynamic blocks on M1

**Registered 2026-11-03, before any DS41 row was collected.** Only procedure has run (`NOTES_PREFLIGHT.md`): downloads
verified by sha256, the Engram tensor hashed in both files, metadata and templates compared, and one smoke test per
build on neutral prompts (`smoke_ds41.sh`; no M1 item sent). Mark approved the downloads and the head-to-head on 11-02.

**Prior art checked:** `ledger_precheck.py "deepseek v4 flash quant comparison GSQ unsloth matched size"` -> receipts found:
- `quant-abstention/RESULT_FLASHNEXT.md` and the scorecard rows: on Flash-Next, GSQ-RCO IQ3_XXS (FNGB) and Unsloth's
  UD-IQ4_XS / UD-Q2_K_XL land within 0.04 on M1 hard accuracy (0.83 / 0.81 / 0.79), but at **different** sizes;
- `bfcl/DS4_FLASH_IQ1S_W3_MATCHED.md`: DeepSeek-V4-Flash IQ1_S on BFCL, ~5 t/s warm on .194;
- INDEX L191: at matched bytes an unpruned 1-bit quant beat a pruned 3-bit by 22.8 pp on knowledge.

**What this adds:** the first M1 arms of DeepSeek-V4.1 (748B-A16B, Engram), and two packagers' builds at **matched
scored bytes**, where the only difference is the backbone's allocation:
- the Engram / PLE table is byte-identical in both (sha256 of the tensor data `36ee7d37...`);
- routed experts 132.07 GB (GSQ) vs 132.21 GB (Unsloth); other backbone tensors 6.16 vs 7.59 GB;
- tokenizer metadata identical in all ten fields; M1 prompts render identically under both embedded templates.

The labels ("IQ2_XXS", "IQ1_M") are not specs (`gguf-label-is-not-a-spec`): the builds are named here by bytes.

## Instrument

- **Host:** .194, 4x Tesla P100 at 150 W / 1063 MHz, read back per arm. One arm at a time, each on a fresh server.
- **Build:** upstream llama.cpp b12063 (`2cbca389`), `~/llama.cpp-b12063/build_sm60`, sm_60, gcc-13 host compiler
  (`build_b12063_sm60.sh`). DeepSeek-V4.1 support: ggml-org/llama.cpp #31086.
- **Server:** `-ngl 99 -sm layer -c 4096 -ctk f16 -ctv f16 -np 1 -fit off --cache-ram 0 --numa distribute
  --reasoning off`, `GGML_CUDA_ALLREDUCE=internal`.
  - **Template:** `--chat-template-file` ISTA's `chat_template.jinja` (sha256 `4d61d22c...`) for **both** arms.
  - **Placement, identical for both arms:** routed experts of layers 0-1, 10-12, 20-22, 30-33 on the GPUs, the other
    28 layers' experts on the CPU (`-ot`). Layer 2 moved to the CPU after the first smoke run ran CUDA0 out of memory.
- **Runner:** `quant-abstention/run_main.py`, corpus M1 (240 items: 40 E, 100 H, 100 U), thinking off, greedy
  (`temperature 0`), `max_tokens` 1024, `--neutral-penalties` (penalties sent explicitly; the Unsloth file carries
  `temp 1.0 / top_p 1.0` defaults, which greedy makes moot), `--usage --timeout 3600`.
  - **`--skip-slot`:** the forced-slot P(UNKNOWN) is not collected. In this tokenizer " UNKNOWN" is not one token, so
    the slot could not measure the main refusal spelling, and it would add a second slow prefill to every item. The
    scorecard's M1 metrics read only the graded answer.
- **Gates (`run_ds41_arms.sh`, abort on failure):** the server answering names the arm's file; the `-ot` override line
  is in its log; every GPU holds >= 8,000 MiB; the command line carries the template and `-ot`; **the 240 rendered and
  tokenized M1 prompts hash the same in every arm as in DS41G** (`prompt_gate.py`); DS41U and DS41GR must match DS41G's
  UNKNOWN-variant ids and render tail.

| arm | file | items |
|---|---|---|
| DS41G | ISTA-DASLab GSQ-RCO IQ2_XXS + Engram (`65d53bc8`), 248.84 GB | M1, 240 |
| DS41U | unsloth UD-IQ1_M (`2688c0c3`), 250.40 GB | M1, 240 |
| DS41GR | DS41G again, fresh server, same placement | `M1R20`: every 12th M1 item (4 E, 8 H, 8 U) |

## Analysis (`analyze_ds41.py`, committed and self-tested before any DS41 row)

Per arm, as `RESULT_FLASHNEXT.md`: E and H accuracy (CORRECT), H abstained, U refused (ABSTAINED; a lenient variant also
counts a bare UNKNOWN), U confabulated (WRONG), unfinished. DS41G - DS41U paired by item: difference, 95 % percentile
bootstrap (10,000 resamples, seed 20261103), exact two-sided McNemar on discordant pairs, grade agreement.

Self-test on stored arms: FNQ2 vs FNIQ4 reproduces `RESULT_FLASHNEXT.md` (E 0.90/0.95, H 0.79/0.81, U 0.71/0.71).

**Power:** with 100 items per group, a paired difference smaller than about 0.10 will rarely reach p < 0.05. A null
result reads as "no detectable difference at this n", not as equivalence.

## Predictions

| # | claim | rule | confidence |
|---|---|---|---|
| P1 | **No detectable knowledge difference at matched bytes** | H accuracy: abs(DS41G - DS41U) <= 0.05 and McNemar p > 0.05 | 0.6 |
| P2 | **No detectable calibration difference** | U refused: abs(DS41G - DS41U) <= 0.07 and McNemar p > 0.05 | 0.6 |
| P3 | **The big model at ~2 bits knows more than Flash-Next at 2 bits** | H accuracy of both arms >= 0.79 (FNQ2) | 0.6 |
| P4 | **A fresh server reproduces the arm** | DS41GR: `content` byte-identical to DS41G on >= 19 of 20 items | 0.8 |

Reported without a prediction: E accuracy; U confabulation; unfinished rate; decode and prefill speed (`--usage`).

## Deviations

Any change to a flag, a file, the placement, the template or the analysis after the first DS41 row gets a numbered
Deviation here, committed before the affected rows are read.
