# Result -- converting GSQ-RCO's 192 BF16 hyper-connection matrices to Q8_0 speeds its decode 1.13x (registered, 20.38 vs 18.02 tok/s) and, with the embedding table cached, matches UD-Q2 exactly (21.06 vs 21.08). It is not free: mean KLD 0.015, top-1 96.5 %. The slow part is the float mat-vec kernel at short rows (F16 and F32 are just as slow), so a kernel fix would give the speed without the fidelity cost.

**2026-09-29.** Pre-registration `PREREG_HC_Q8.md` (`513a721`), with Deviation 2 (below). Runner `run_hc_q8.sh`, build
`hc_build.sh`, probe `hc_probe.py`, analysis `analyze_hc_q8.py`, output `RESULT_hc_q8.json`.

- **Raw:** `raw_hc/`: `perf_hc_E_r{1,2,3}.txt`, `decode.jsonl` (24 rows with content), `kld_base.txt`,
  `kld_hcq8.txt`, `kld_self_control.txt`, server logs, `run.log`.
- **Host:** .194 at 150 W / 1063 MHz (read back), buun `0b2789f23`. The test build left the fleet libraries' md5
  (`ad5746184b2f`) and the source tree unchanged.

## The intervention

- `tools/gguf_retype.py` rewrote shard 1 of the ISTA-DASLab GSQ-RCO IQ3_XXS base:
  - **192 tensors** (`hc_{attn,ffn}_{up,down}`), BF16 -> Q8_0, 1,258.3 MB -> 668.5 MB;
  - **1,031 copied tensors, 0 hash mismatches**;
  - shard 1 went from 47,039,860,096 to 46,450,036,096 bytes, sha256 `1b01bec416cd0910…`; shard 2 is a symlink to
    the original.
- **The server confirms it:** `type q8_0: 192 tensors`, and BF16 drops from 484 to 292 tensors.

## Registered verdicts

| # | claim | result |
|---|---|---|
| H1 | HCQ8 >= 1.07x GSQB (bracketing run) | **holds.** 20.38 vs 18.02 tok/s, 1.131x |
| H2 | HCQ8 within 3 % of UD-Q2 | **does not hold as registered.** 0.967 (the medians include warm-up; see below) |
| H3 | F16 >= 2x Q8_0 at k=320, m=10240 | **holds.** 82.2 vs 23.0 us, 3.57x |
| H4 | mean KLD(HCQ8 vs GSQB) < 0.01 | **does not hold.** 0.0153 +/- 0.0007 |

## Kernel control (3 reps at 1063 MHz)

| shape | F16 | F32 | BF16 | Q8_0 |
|---|---:|---:|---:|---:|
| `hc_up`: k=320, m=10240 | 82.2 us | **80.3 us** | 82.1 us | **23.0 us** |
| `hc_down`: k=10240, m=320 | 21.2 us | 28.8 us | 21.0 us | 15.6 us |

**At k=320 all three float types take the same time, and F32 moves twice F16's bytes.** So this is not BF16 and not
bandwidth. It is how the float mat-vec kernel (`mmvf.cu`) launches: one thread block per output row, sized to the row
length. That gives 10,240 blocks of 160 threads, each doing one multiply-add per thread and then a cross-warp
shared-memory reduction. Per-block overhead dominates. The quantized kernel handles short rows differently and is
3.6x faster.

## Decode

**Registered medians (12 requests each):**

| arm | median |
|---|---:|
| HCQ8 | 20.38 tok/s |
| GSQB, bracketing run | 18.02 tok/s |
| UD-Q2, kernel run (24 rows at 1063) | 21.08 tok/s |

**Post-hoc: first vs second pass of the same prompts.** Not a registered verdict. `NOTE_WARMUP_DIAGNOSIS.md` shows the first pass is slow because of page faults on the mmapped embedding table, not warm-up. The second pass is the rate with those rows cached.

| arm | first pass (rows faulting) | second pass (rows cached) |
|---|---|---|
| **HCQ8** | 18.6-19.7 | **21.04-21.08** |
| UD-Q2 (kernel run, first block) | 18.7-19.8 | **21.05-21.08** |
| GSQB (kernel run, first block) | 17.0-17.8 | **18.80-18.84** |
| GSQB (bracketing run) | 17.4-18.8 | 17.8-18.7, never settled |

- **With the table cached, the converted file decodes at UD-Q2's speed, to 0.1 %**: 21.06 vs 21.08. That is 1.118x
  the original GSQ-RCO's cached 18.83, which comes from the kernel run's server and cache state, not this run's bracket.
  The ~6 ms/token the kernel model assigned to the hyper-connections is all of the gap.
- H2 fails as registered: HCQ8's first pass was faulting, UD-Q2's reference was mostly cached. The bracketing GSQB
  never reached the cached rate because a different model generates different tokens after heavy page-cache churn.

**Greedy outputs:** 2 of 12 identical between HCQ8 and GSQB. The rest first differ at characters 187-747. Each arm is
deterministic: rep 1 and rep 2 match within an arm.

## Fidelity (wikitext-2 test, 16 x 512)

| | HCQ8 vs GSQB | GSQB vs itself (Deviation 2 control) |
|---|---:|---:|
| mean KLD | **0.0153 +/- 0.0007** | 0.000000 |
| median KLD | 0.0017 | 0.000000 |
| 99th percentile KLD | 0.197 | 0.000035 |
| same top token | **96.52 %** | 100.00 % |
| PPL ratio | 0.9925 +/- 0.0034 | -- |

- **The noise floor is zero,** so the 0.0153 is the conversion's.
  **Forward note (10-02, `RESULT_MMVF_SHORTROW.md`):** the zero is only the same-path floor. Two legitimate code paths
  of one unmodified build (`-ub 512` vs `-ub 1`) diverge by 0.0144 on this model, and a summation-order kernel change
  by 0.0139. So much of this 0.0153 may be amplification, not Q8_0 precision. It cannot be separated after the fact.
- For scale: GSQ-RCO IQ3_XXS itself sits at ~0.115 KLD from its BF16 original on English prose (ISTA's number, a
  different corpus). The conversion adds roughly a tenth of that. Perplexity moved slightly *down*, which is why
  PPL is the wrong instrument here.
- **The hyper-connections are sensitive.** They mix the four residual streams in every layer. BF16 -> Q8_0 on just these
  192 tensors changes the top token 3.5 % of the time. ISTA keeping them at BF16 looks deliberate on fidelity grounds.
  bartowski's map stores them as Q4_K and Q5_0; its fidelity cost there was not measured.

## What it means

- **The GSQ-RCO speed penalty on sm_60 is fully explained and fully removable:** 192 BF16 matrices, one bad kernel
  shape, and a conversion recovers every token per second.
- **The conversion is a trade, not a free fix.** For +12 % decode it costs KLD 0.015 and 96.5 % top-1 agreement.
- **The better fix is the kernel.** F16/F32/BF16 mat-vec at short rows is 3.6x slower than it needs to be. Putting
  multiple rows per block (a warp per row, with a warp-only reduction) when rows are short would keep the BF16 bits and
  should recover most of the speed. That would help any model with short-row float matmuls. It is the next step and
  a candidate upstream contribution. **Done 10-01:** `RESULT_MMVF_SHORTROW.md` (hc_up BF16 3.0x faster, no conversion).

## Deviations

- **Deviation 2 (post-hoc, after all registered rows):** the GSQB-vs-GSQB KLD control was added after H4 failed, to
  measure the noise floor (`raw_hc/kld_self_control.txt`, same flags and base file). It is reported next to H4 and
  does not change H4's verdict. It is recorded in the prereg too.

## Not established

- One file, one GPU model. The kernel's short-row cost on Volta or later was not measured.
- KLD on 8,192 wikitext tokens at c=512; no task-level evaluation of the converted file.
