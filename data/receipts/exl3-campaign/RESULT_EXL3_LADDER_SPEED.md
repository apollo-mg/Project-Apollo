# Result — the decision table: GGUF is faster at every quality level, EXL3 is smaller at every quality level

**Run 2026-09-12, 20:54–21:16, on `.73`.** Pre-registered in `PREREG_EXL3_GGUF_LADDER_SPEED.md`
(`b0b669c`) with Amendment 1 (`b63a628`), scored by `tools/score_exl3_ladder.py`, committed with the
prereg. Raw data in `ladder/`. EXL3 campaign test 7, ledger O5.

Speed measured under the daily driver's exact flags, as in test 1. **KLD comes from test 3**, measured at
`-ub 8` under `-sm layer` — **a different configuration**, and the two columns must be read as such.

## The table

| option | served t/s | greedy t/s | acceptance | prefill t/s | mean KLD | VRAM (test 3) |
|---|---|---|---|---|---|---|
| **UD-IQ4_XS** | **24.60** | 26.96 | 0.767 | 134.8 | 0.015727 | 13,500 MiB |
| **UD-Q4_K_M** | 23.13 | 24.10 | 0.686 | 140.5 | 0.007840 | 15,448 MiB |
| **Q6_K**, the daily driver | 20.25 | 22.38 | 0.692 | 151.2 | 0.002770 | 21,276 MiB |
| **EXL3 5.00bpw** | 14.14 | 14.30 | 0.658 | **159.9** | 0.003994 | 16,372 MiB |
| **EXL3 4.00bpw** | 13.08 | 13.96 | 0.693 | 153.7 | 0.012002 | 13,468 MiB |

| id | prediction | result |
|---|---|---|
| P-G1 | all three new arms load and read the vision probe | **CONFIRMED** |
| P-G2 | both GGUFs decode faster than EXL3 4.00bpw | **CONFIRMED.** 24.60 and 23.13 vs 13.08 |
| P-G3 | UD-IQ4_XS decodes faster than UD-Q4_K_M | **CONFIRMED.** 24.60 vs 23.13 |
| P-G5 | UD-Q4_K_M beats EXL3 4.00bpw outright | **CONFIRMED.** Faster (23.13 vs 13.08) and closer (0.0078 vs 0.0120) |
| P-G6 | EXL3 5.00bpw decodes slower than 4.00bpw | **FALSIFIED.** It is *faster*: 14.14 vs 13.08 |
| P-G7 | UD-Q4_K_M decodes faster than EXL3 5.00bpw | **CONFIRMED.** 23.13 vs 14.14 |
| P-G8 | no EXL3 arm beats every GGUF arm on speed **and** KLD together | **CONFIRMED** |

## Two findings worth more than the verdicts

**1. More bits made EXL3 faster, and the source suggests why.** EXL3 5.00bpw carries 22% more weight
bytes than 4.00bpw and still decodes 8% quicker. In buun's int8 kernel, **shared-memory row staging turns
on only at 5 bits and above**: `stage_smem(bits) { return bits >= 5; }`, with the comment *"pair-row
staging depth (rows in flight per warp) for the smem unit (K = 5..8)"* (`exl3-gemv-int8.cuh:53-56`).
**Hypothesis, untested:** the 4-bit path skips staging and pays for it. If that holds, buun's 4-bit
kernel is leaving throughput on the table, and the fix would help the bitrate most people use. **The
test:** time 4.00 and 5.00bpw at `-ub 1` in llama-bench (test 4's harness), where staging is the only
structural difference.

**2. EXL3 prefills fastest of everything measured** — 159.9 t/s at ~15k tokens, against Q6_K's 151.2 and
IQ4_XS's 134.8. Prefill-heavy work (agents, long prompts) does not pay the decode penalty.

## What this means for `.73`

**The daily driver is already the better choice on this box, and that is not a criticism of EXL3.**
Q6_K is *both* faster than EXL3 5.00bpw (20.25 vs 14.14) *and* closer to the reference (0.00277 vs
0.00399). It costs 4.9 GB more VRAM — and `.73` has 32 GB across two cards, so that VRAM is not scarce.

**EXL3 converts VRAM into fidelity, and this node has VRAM to spare.** Its advantage becomes real where
VRAM binds:
- **A 16 GB single card**, where Q6_K's 21 GB does not fit at all.
- **Long context**, if VBR needs the freed 8 GB to hold a higher KV tier — untested, and now the most
  decision-relevant open item (`PREREG_EXL3_LONGCTX.md`).
- **The RDNA4 box**, which cannot run EXL3 at all today (O1).

**The honest summary of the campaign so far: EXL3 wins quality-per-byte and loses quality-per-second,
and whether that trade is worth making depends entirely on which resource is scarce.**

## Deviations and limits

- **Speed and KLD come from different configurations.** Speed here is `-sm tensor` with VBR KV at 262k;
  KLD is `-ub 8` with f16 KV at 512 under `-sm layer`. Neither column is wrong, but they are not one
  experiment.
- **The two prior rows (EXL3 4.00bpw and Q6_K) are test 1's numbers**, measured on the same node, binary,
  flags and prompt earlier the same day.
- **Load times are not comparable:** EXL3 loads from spinning disk, the GGUFs from NVMe — 301 s against
  202 and 232 s.
- **VRAM here differs from the KLD column** because this test runs 262k VBR context with an mmproj:
  E5s 20,630 MiB, G4s 17,994, G5s 19,942.
- **One prompt, 256 tokens, three reps per arm.**
- **The first attempt aborted on a wrong size constant** (the HF listing's all-files total instead of the
  safetensors sum). It refused to run rather than proceed unverified; no data came from it.
