# Pre-registration: Strata on 4x P100 (its experimental Pascal path) against our dialed-in llama.cpp, on the SAME Flash-Next weights, with speculation matched

**Registered 2026-10-06, before any timed row.** BACKLOG N19 (Mark: "sounds like a good plan"; 10-06: "happy to boot
it up if you wanna look at installing Strata on it").

**Prior art checked:** `ledger_precheck.py "Flash-Next MTP speedup ncmoe expert spill offload verify batch cost"` and
the 10-05 desktop run. Receipts found:
- **`strata-9070/` (10-05):** Strata's adaptive cache hits 83 % of lookups with ~40 % of the experts on a 16 GB card.
  There, Strata's lead over llama.cpp could not be split into cache and speculation: the Coder GGUF had no
  llama.cpp-usable MTP.
- **INDEX L438:** llama.cpp MTP under heavy offload is only 1.30-1.44x.
- **qwen4exp/split-conc (10-01):** our best single-user .194 config, tensor split + MTP draft 3 (`-ts 1,1,1,0.75`,
  `-ub 512`), decodes UD-Q2_K_XL at 27.4 tok/s.
- **What this adds:**
  - the first Strata numbers on a P100 (their docs: "not measured");
  - the first engine comparison with speculation matched, since a llama.cpp-usable Flash-Next MTP file exists here;
  - a box where Strata's whole expert arena (42.9 GB for IQ3_XXS) fits in the 64 GB of VRAM, so the cache should
    hold nearly everything.

## Instrument

- **Host:** .194, 4x Tesla P100-PCIE-16GB (sm_60, driver 580.173.02), 2x Xeon E5-2650 v3, 121 GB RAM.
  - Clocks: NOT re-pinned after the reboot (idle 405 MHz, max 1,328, 150 W).
  - Live SM clocks are recorded during every arm. Both engines share one clock state.
- **Weights (both engines):** ISTA-DASLab `Qwen3.8-Flash-Next-GSQ-RCO-GGUF` IQ3_XXS.
  - Both shards are sha256-verified on .194 against the revision Strata pins (`ed59f92`): `219ea929…`, `316b46f3…`.
  - That is ~3.06 bpw with all 512 experts.
- **Strata:** v0.1.39 (tag at `a1641e9`; the engine is the same as the desktop's `6f32ec0`, and the tag move was a
  setup tip). Its CUDA 12 engine was built here with CUDA 12.4 + gcc-13 (`-DSTRATA_EXPERIMENTAL_SM60=ON`).
  - Installer config for `--gpus 0,1,2,3 --cuda 12 --model IQ3_XXS --gguf-dir fn_gsq_base`, vision off.
  - Thinking off through its shared setting (`reasoning_effort: none`), deleted after the runs.
- **llama.cpp:** buun `0b2789f23` (`~/buun-0b278/build_sm60`), the same IQ3_XXS shards.
  - Drafter: `flashnext_mtp/mtp-Qwen3.8-Flash-Next-shared-Q8_0.gguf` (2.79 GB), draft 3.
  - The split-conc T3 recipe: `-sm tensor -ts 1,1,1,0.75 -ngl 99 -fa on -ub 512`.
  - `--reasoning off`, f16 KV, `-c 8192 -np 1`.
  - **Fallback if it does not load:** layer split + MTP (`-sm layer`), as recorded.
- **Measurement:** `lmx` v0.1.48 (official binary, copied to .194), remote mode against localhost.
  - Canonical prompts reasoning-v1 and code-v1; temperature 0, 256 tokens, 1 warmup + 3 timed, median.
  - `g4_proxy.py` captures the evidence.
  - Strata's per-request hit rate and draft counts come from its log; llama.cpp's draft counts from its timings.
- **Gates:** captured `content` non-empty; 256 completion tokens; the drafter active (draft counts above 0) in every
  MTP arm.

## Arms

| arm | engine | prompt | starts |
|---|---|---|---|
| **S_r** | Strata | reasoning-v1 | 2 |
| **S_c** | Strata | code-v1 | 1 |
| **L_r** | llama.cpp + MTP (draft 3) | reasoning-v1 | 2 |
| **L_c** | llama.cpp + MTP | code-v1 | 1 |
| **L0_r** | llama.cpp, no drafter | reasoning-v1 | 1 |

## Predictions

| # | claim | confidence |
|---|---|---|
| P1 | Strata's decode hit rate is at least 95 % (the whole arena fits in VRAM) | 0.6 |
| P2 | Strata decodes faster than llama.cpp + MTP on reasoning-v1 (median of the S_r starts > median of the L_r starts) | 0.4 |
| P3 | llama.cpp + MTP decodes at least 1.4x llama.cpp without a drafter (fully resident here, unlike L438's offload) | 0.6 |

## Reporting

- Every arm's medians, samples, TTFT, prompt tokens, draft and accept counts, hit rate and live SM clocks.
- Nothing is submitted without Mark's OK.
- **Strata's P100 path is experimental.** A crash or wrong output is a result and is reported as one.

## Not tested

- Quality.
- Long contexts.
- Strata's other packs.
- The desktop.

## Deviations

Any change after the first timed row gets a numbered Deviation here before the affected rows run.
