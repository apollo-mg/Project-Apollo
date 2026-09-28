# Pre-registration -- Flash-Next on the quant-abstention instrument: does a 2-bit big MoE know more than an 8-bit 27B, and does its calibration hold?

**Registered 2026-09-28, before any Flash-Next row was collected.** Only a feasibility boot has run: the Q2_K_XL arm
loaded on .194 with the build below. Its tokenizer maps " UNKNOWN" / " Unknown" / " unknown" to 59322 / 21024 / 9496,
the same ids as Qwen3.8-27B. One smoke request ("17*19", thinking off) answered `323`. No M1 item has been sent.

**Prior art checked:** `ledger_precheck.py "Flash-Next quant quality Q2_K_XL IQ4_XS abstention behaviour"`. It
found:
- INDEX L149, "quantisation degrades KNOWLEDGE before CALIBRATION" (the AD ladder, 27B);
- `RESULT_MAIN.md`, 23 arms of Qwen3.8-27B on this corpus and instrument. On it, UD-Q2_K_XL loses 15 points of
  hard-question accuracy against Q8_0 (0.35 vs 0.50) while refusals on invented items do not move (0.61 vs 0.60);
- `qwen4exp/RESULT_STRUCTURAL_TENSOR_AUDIT.md`: the Flash-Next quants keep all five qwen4exp structural tensor
  classes in F32.

**What this adds:**
- the first model outside the 27B on this instrument, and it is a different architecture (qwen4exp MoE);
- the same knowledge-vs-calibration question asked inside it, Q2 vs IQ4;
- the practical cross-model question for this fleet: does Flash-Next at 2 bits (on .194) know more than the 27B at
  8 bits?

## Instrument (as `PREREG_MAIN.md`, except where stated)

- **Host:** .194, 4x Tesla P100 at the fleet efficiency config (150 W, 1063 MHz), read back and recorded per arm.
- **Build:** buun `0b2789f23`, `~/buun-0b278/build_sm60`, the main campaign's build.
- **Server flags:** `-ngl 99 -sm layer -c 4096 -ctk f16 -ctv f16 -np 1 -fit off -lv 4`, `GGML_CUDA_ALLREDUCE=internal`,
  all four GPUs (main used two per lane; Flash-Next does not fit two). One arm at a time. Every arm starts on a
  fresh server, and one warm-up request is discarded before the run (`server-uptime-is-a-variable`).
- **Runner, corpus and grading:** `run_main.py`, `corpus/M1` (240 items: 40 E, 100 H, 100 U), thinking off,
  `max_tokens` 1024.
  - `--expect-variants` enforces the three UNKNOWN ids.
  - The render tail is recorded but not enforced, since the 27B's tail need not match another model's template.
- **Arms:**

| arm | file | placement |
|---|---|---|
| FNQ2 | `Qwen3.8-Flash-Next-UD-Q2_K_XL` | fully GPU-resident |
| FNIQ4 | `Qwen3.8-Flash-Next-UD-IQ4_XS` | the smallest expert spill that loads: routed experts of the last K layers on CPU via `-ot`, starting at K = 4 (layers 44-47) and stepping by 2 |
| FNQ2X | `UD-Q2_K_XL` | **placement control:** the same `-ot` spill as the final FNIQ4 |

- **27B reference:** the stored `raw/main_C.A.jsonl` (Q8_0) and `raw/main_UDQ2KXL.jsonl`, same corpus and runner.

## Readouts and analysis (`analyze_flashnext.py`, committed before any Flash-Next row is opened)

The primary readout is **the written answer** (AFM-48: a forced-slot shift is not a behaviour shift):
- E and H accuracy: share of items graded CORRECT;
- H timidity: ABSTAINED on H;
- U refusal: ABSTAINED on U. Its complement is confabulation.

TRUNCATED counts as not correct and not refused.

Differences are paired by item. 95 % intervals come from a percentile bootstrap over items (10,000 resamples,
seed 20260928). The forced-slot P(UNKNOWN) is reported as secondary, with generation-vs-slot kappa as in main.

## Predictions

| # | claim | rule | confidence |
|---|---|---|---|
| P1 | **Knowledge before calibration, inside Flash-Next** | H accuracy FNIQ4 - FNQ2 >= 0.05 with 95 % CI lower bound > 0, **and** U refusal FNQ2 - FNIQ4 within +/-0.07 | 0.6 |
| P2 | **Scale buys knowledge** | H accuracy FNIQ4 - 27B Q8_0 >= 0.05, CI lower bound > 0 | 0.7 |
| P3 | **The 2-bit big MoE knows at least as much as the 8-bit 27B** | H accuracy FNQ2 - 27B Q8_0 >= 0, CI lower bound > -0.05 | 0.6 |
| P4 | **Placement is numerically inert for behaviour** | FNQ2 and FNQ2X give the same grade on >= 95 % of items | 0.8 |

Reported without a prediction:
- U refusal of each Flash-Next arm against the 27B Q8_0's 0.60. A bigger model could confabulate more or less.
- E accuracy.
- Speed and power, recorded for BACKLOG N11 but not claimed.

## Deviations

Any change to a flag, a file, a placement rule or the analysis after the first M1 row gets a numbered Deviation
here, with its reason, before the affected arm runs.
