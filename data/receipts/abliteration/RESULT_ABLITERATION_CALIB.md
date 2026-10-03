# Result -- OrcaRouter's abliteration of Qwen3.8-27B barely moves ordinary text (KLD 0.004) and keeps the model as honest as before, but costs 3.5 pp of factual recall; and the "proprietary" OrcaSAQ2 quant is indistinguishable from plain IQ4_XS of the same weights (KLD 0.0184 vs 0.0173, knowledge +1.2 pp p=0.26) while 370 MB larger.

**2026-10-03.** Pre-registration `PREREG_ABLITERATION_CALIB.md` (`f3fdae79`).
- **Deviation 1** (`63f961d8`): KLD reran with `-b 512`. Without it, `llama-perplexity` packed 4 sequences and
  silently evaluated nothing on this hybrid model. Fixed before any KLD row.

Runner `run_abl.sh`, analysis `analyze_abliteration.py` (self-tested), output `RESULT_abliteration.json`.

- **Raw:** `raw/<ARM>/{ikp.jsonl, m1.jsonl, server.log}`, `raw/kld_*.txt`, `raw/run.log`.
- **Host and build:** .194 split into two 2-GPU halves (socket-bound), buun `0b2789f23`. `-c 8192 -np 1`, f16 KV,
  thinking off, no MTP.
- **Gates:** every arm passed 66/66 layers on GPU, f16 KV, thinking off, and M1's UNKNOWN token ids.
- **Files:** all four sha256-verified against HF / the daily file.

## Results

| arm | file | KLD vs U6 (top-1) | IKP correct | IKP fabrication | IKP refusal | M1 easy / hard / hard-wrong | M1 invented declined |
|---|---|---|---:|---:|---:|---|---:|
| **S6** | stock Q6_K (.73 daily), 22.88 GB | 0.0042 (97.1 %) | **63.4 %** | 22.4 % | 2.1 % | 0.85 / 0.52 / 0.45 | **0.63** |
| **U6** | OrcaRouter abliterated Q6_K, 22.43 GB | reference | 59.9 % | 22.6 % | 0.7 % | 0.825 / 0.50 / 0.47 | 0.55 |
| **U4s** | OrcaSAQ-2 "Cyber" (abliterated), 15.68 GB | **0.0184** (94.3 %) | 55.0 % | 25.1 % | 1.0 % | 0.825 / 0.47 / 0.52 | 0.55 |
| **U4x** | OrcaRouter abliterated plain IQ4_XS, 15.31 GB | **0.0173** (94.2 %) | 53.8 % | 24.1 % | 1.0 % | 0.825 / 0.47 / 0.48 | 0.525 |

**Paired tests** (exact McNemar, IKP correct / M1 invented-declined):

| contrast | IKP correct (only A / only B, p) | M1 invented declined (only A / only B, p) |
|---|---|---|
| S6 vs U6 | 40 / 15, p = 0.001 | 10 / 3, p = 0.09 |
| U6 vs U4s | 52 / 17, p = 3e-5 | 3 / 4, p = 1.0 |
| U6 vs U4x | 56 / 12, p = 6e-8 | 5 / 3, p = 0.73 |
| U4s vs U4x | 30 / 21, p = 0.26 | 6 / 3, p = 0.51 |
| S6 vs U4s (the downloaded file vs the daily driver) | 75 / 15, p = 9e-11 | 10 / 2, p = 0.04 |

## Registered verdicts

| # | claim | result |
|---|---|---|
| A1 | abliteration lowers invented-item abstention by >= 0.15 | **does not hold.** -0.08 (0.63 -> 0.55, p = 0.09) |
| A2 | abliteration raises fabrication by >= 5 pp | **does not hold.** 22.4 -> 22.6 % |
| A3 | abliteration keeps knowledge within 3 pp | **does not hold, narrowly.** -3.5 pp (p = 0.001) |
| A4 | abliteration barely moves ordinary text (KLD < 0.05) | **holds.** 0.0042 mean, 97.1 % top-1 |
| R1 | SAQ2 beats plain IQ4_XS at matched size (KLD <= 0.8x) | **does not hold.** 0.0184 vs 0.0173 (1.06x) |
| R2 | the card's fidelity roughly holds (KLD vs U6 <= 0.030) | **holds.** 0.0184 (card: 0.020 vs BF16) |
| R3 | SAQ2 keeps U6's calibration and knowledge | **does not hold.** Calibration is kept (0.55 vs 0.551), but knowledge is -4.9 pp |

**Contrast caveat (registered):** S6 vs U6 is weights plus recipe. OrcaRouter's Q6_K quantizes 145 recurrent-gate
tensors that the daily file keeps in F32 / Q8_0. The whole difference is a KLD of 0.004, so the recipe part is
small, but it is not separated.

## What it means

- **This abliteration is careful.**
  - Next-token predictions on ordinary prose barely change (KLD 0.004, 97 % same top token).
  - Fabrication does not rise. Abstention on invented entities dips slightly (-0.08, not significant).
  - Refusals fall from 2.1 % to 0.7 %, which is the purpose.
  - The measurable cost is factual recall, -3.5 pp, concentrated in T1/T2 (86 -> 80.5 %, 78 -> 75.5 %).
  - This fits modern KL-constrained abliteration rather than 2024-style direction removal.
- **OrcaSAQ2's claims, checked:**
  - "~3 bit footprint": no, it is IQ4_XS-sized (15.68 vs 15.31 GB).
  - "Significantly better capacity retention": not at matched size. The same KLD (median 0.0073 both), the same
    top-1, and knowledge and calibration within noise of plain IQ4_XS of the same weights.
  - The card's 0.020 KLD is consistent with our 0.018 against Q6_K, but plain IQ4_XS gets the same.
- **4.5-bit quantization costs knowledge before calibration:** -4.9 / -6.1 pp IKP against Q6_K, with M1 calibration
  unchanged. That replicates quant-abstention (INDEX L156) on this model.
- **For Mark's downloaded file against his daily driver:** -8.4 pp factual recall (p = 9e-11) and a little less
  abstention on invented entities (0.63 -> 0.55, p = 0.04).
  - That is reasonable for a 15.7 GB uncensored model.
  - The honest framing is "uncensored and smaller", not "lossless".
  - OrcaRouter's plain IQ4_XS gives the same thing for 370 MB less.

## Not established

- **Cybersecurity skill and behaviour on harmful requests** (out of scope; "Cyber" appears to be branding).
- **Sycophancy,** which none of these batteries measure.
- **Thinking on.**
- **BF16 references.** U6, a Q6_K, stands in for BF16.
- **Whether the 3.5 pp is abliteration or the gate-tensor recipe.** That needs a stock Q6_K made with OrcaRouter's
  recipe.
- **240 M1 items per arm** is under-powered for differences under ~0.1.
