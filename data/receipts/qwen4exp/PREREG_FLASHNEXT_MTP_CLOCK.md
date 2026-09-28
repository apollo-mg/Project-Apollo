# Pre-registration: MTP on a fully resident Flash-Next, and whether the P100 clock pin costs it more than it costs plain decode

**Registered 2026-09-28, before any row.** Mark: "we normally run power constrained. But those constraints were built
on a power efficiency curve that I believe we built without speculative decoding in mind." BACKLOG N11 and Flash-Next
track 3.

**Prior art checked:**
- `RESULT_FLASHNEXT_MTP_OFFLOAD.md` (09-02, written up today): MTP gave 1.30x / 1.44x under `-ncmoe 44`, acceptance
  0.75, 2.49 tokens per step.
- `RESULT_FLASHNEXT_RESIDENCY.md`: fully resident Q2 reaches 21.05 tok/s without MTP.
- `dflash-pascal/RESULT_S2_DFLASH_PASCAL.md` (08-18, the 27B on .73 with MTP): the 150 W cap never bound, the
  1063 MHz pin bound in every sample, and MTP added 17-22 % busy power.
- The 07-16 plain-decode sweeps behind `p100-efficiency.service` (memory `gpu-clock-benchmark-discipline`): the pin
  gave +25 % tok/J at 84 % of the speed.

**What this adds:**
- MTP on Flash-Next with every expert in HBM, not host memory;
- the first clock and power measurement taken WITH speculative decoding on this fleet;
- the cap and the clock varied separately.

## Instrument

- .194, buun `0b2789f23` (`~/buun-0b278/build_sm60`), Flash-Next UD-Q2_K_XL, `-ngl 99 -sm layer -c 8192 -ctk f16
  -ctv f16 -np 1 -fit off`, all 4 P100s.
- MTP on: `-md mtp-Qwen3.8-Flash-Next-shared-Q8_0.gguf --spec-type draft-mtp --spec-draft-n-max 3`, the 09-02 draft
  depth.
- One fresh verified server per MTP setting (AFM-50 checks). One discarded warm-up; under MTP it must show
  `draft_n > 0`.
- **GPU configs,** switched live and read back per block:

| cfg | cap | application clock | isolates |
|---|---|---|---|
| E | 150 W | 715 / **1063** | today's fleet config |
| P | 150 W | 715 / **1328** | E to P: the clock alone |
| B | **250 W** | reset (autoboost) | P to B: the cap |

- **Order and workload:**
  - Blocks run E, P, B, B, P, E per MTP setting, MTP off first.
  - Each block runs 6 fixed prompts (prose, explanation, code, JSON extraction, arithmetic, a list; `run_mtp_clock.py`
    holds them verbatim), temp 0, thinking off, 384 tokens, `cache_prompt: false`.
  - Each block also runs one cold ~6k-token prefill (`max_tokens` 1).
- **Power:** one `nvidia-smi` sampler at 200 ms for all 4 GPUs (own PID, checked by comm). Request windows are aligned
  with a measured clock offset. tok/J = generated tokens / (mean summed power x window).
- **The efficiency config is restored on exit, always,** and read back.

## Predictions (`analyze_mtp_clock.py`, committed with this file, self-tested on synthetic data)

| # | claim | rule | confidence |
|---|---|---|---|
| M1 | **MTP pays off when the experts are resident** | decode(MTP on) / decode(MTP off) at E >= 1.4 | 0.55 |
| M2 | **The pin costs MTP more than plain decode** (Mark's hypothesis) | (P/E decode ratio, MTP on) - (P/E decode ratio, MTP off) >= 0.05 | 0.55 |
| M3 | **The 150 W cap still does not bind for decode** | B vs P decode within +/-3 %, both MTP settings | 0.6 |
| M4 | **The pin's efficiency edge shrinks under MTP** | tok/J(E)/tok/J(P) - 1 >= 0 with MTP off, and smaller with MTP on | 0.5 |

Reported without a prediction:
- prefill by config (compute-bound, so the clock should show most there);
- acceptance and tokens per step against the 09-02 offload run;
- per-config mean power.

**Scope:** decode medians over 12 requests per cell and one model. Layer split on 4 GPUs is a pipeline, so one GPU
works at a time; whole-box power per token is what is measured, not per-GPU efficiency.

## Deviations

Any change after the first row gets a numbered Deviation here before the affected rows run.
