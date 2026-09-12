# Prereg — KL divergence: where EXL3 sits on a GGUF size curve (EXL3 campaign, test 3, ledger O6)

**Written 2026-09-12 ~16:00, before any KLD data.**

## Question

Perplexity put EXL3 4.00bpw at +0.55% against the Q6_K. That is one number, and it hides which tokens
moved. KL divergence against a higher-precision reference measures the whole next-token distribution at
every position.

The campaign's question is sharper than "is EXL3 close to Q6_K?" **At a matched size, does EXL3 stay
closer to the model than GGUF does?** That is the "more quality in the same bits" claim.

## Setup

- **Node:** `.73`, both P100s. The wake proxy is paused (`orchestrate_kld.sh`), with a dead-man timer.
- **Binary:** QUAL, `~/buun-sm60-qual/build_sm60qual`, which is buun `9ae8f0f40` plus the e8m0 guard.
  Tool: `llama-perplexity`.
- **Text:** wikitext-2-raw test, `/mnt/HDD/exl3/wiki.test.raw`, 1,290,590 B, sha256 `173c87a5…9e7dd08`.
- **Flags for every run:** `-ngl 99 -sm layer -c 512 -b 512 -ub 8 --chunks 40 -fa on -ctk f16 -ctv f16`.
  - `-c 512 --chunks 40` matches the inference receipt's perplexity.
  - **`-ub 8` keeps every matmul on the small-batch kernels:** MMVQ for GGUF, the int8 path for EXL3.
    Those are the kernels that serve decode.
  - `-ub 8` also avoids the fp16 dequantisation pool that OOM'd the Q6_K at `-sm layer` this morning,
    and lets the 29 GB Q8_0 fit on two 16 GB cards.
- **Reference:** the Q8_0 from `unsloth/Qwen3.8-27B-GGUF` @ `4ca72078` (29,047,086,048 B), run with
  `--kl-divergence-base`.
  - **It is a reference, not ground truth.** Every KLD here is a distance from Q8_0. The comparisons that
    matter are differences between distances to the same reference.
- **Weights:**
  - **One repo for all four GGUFs:** three at commit `4ca72078`, while the Q6_K is the daily driver's
    withdrawn upload (`db81afd1e1`).
  - **Hash checks:** files copied to `.73` for this test are re-hashed there against their published LFS
    sha256 before any run. The EXL3 shards and the Q6_K were hash-verified on `.73` earlier today, so they
    are size-checked instead.

| arm | weights | disk | role |
|---|---|---|---|
| REF | Q8_0 | 29.05 GB | writes the reference |
| R2 | Q8_0, again | 29.05 GB | instrument check: is the reference reproducible? |
| E | turboderp EXL3 4.00bpw | 16.88 GB (13.40 GB reaches the GPU) | the candidate |
| G4 | UD-IQ4_XS | 14.25 GB | GGUF, smaller |
| G5 | UD-Q4_K_M | 16.46 GB | GGUF at EXL3's disk size |
| G6 | Q6_K, the daily driver | 22.88 GB | GGUF, larger |

**Run order:** REF, R2, E, G4, G5, G6.

**Size basis, named in advance.** VRAM is what limits a P100, so each arm's size is its **peak VRAM during
the run**, summed over both GPUs and sampled every 2 s. At `-c 512 -ub 8` the KV and compute buffers are
small, so the peak is close to the weights. Disk bytes are reported alongside.

## Measures

All measures are llama-perplexity's own output:
- Mean KLD, with its reported uncertainty
- Median KLD and 99.0% KLD
- Same top p, with its reported uncertainty
- Mean PPL(Q)

## Predictions

| id | prediction |
|---|---|
| P-K0 | **Gate.** R2's mean KLD is below 1e-4 and its same-top is at least 99.9%. If not, the reference is not reproducible, and every prediction below is **VOID** |
| P-K1 | E's mean KLD is below G5's: EXL3 beats the GGUF of its disk size |
| P-K2 | E's mean KLD is below G4's |
| P-K3 | G6's mean KLD is below E's: 6.6 bits still beat 4 |
| P-K4 | E's same-top is at least 95.0% |

**A difference counts only if two mean KLDs differ by more than the sum of their reported
uncertainties.** Otherwise the prediction is scored **TIE**, not CONFIRMED or FALSIFIED.

**The headline is descriptive, with the rule fixed now:**
- Place the four quantized arms at (peak VRAM, mean KLD).
- **EXL3 "sits below the GGUF curve"** if its mean KLD is below the log-linear interpolation between the
  two GGUF arms whose peak VRAM brackets EXL3's.
- If no two GGUF arms bracket it, say so, and report only the dominance relations: lower KLD at lower or
  equal VRAM.

## Declared in advance

- **One text, one context length, 40 chunks (about 10,200 scored tokens).** Wikitext is not the daily
  driver's workload. Task accuracy is the second half of ledger entry O6, and a separate test.
- **`-ub 8` measures the decode kernels only.** KLD on the prefill kernels (the default `-ub 512`) could
  differ, and is not tested here.
- **The Q6_K is a different upload revision from the other GGUFs,** and unsloth's recipes change between
  uploads (see the "Q6_K is not a spec" memory).
- **The dev-diary ledger's 17:05 run will fail** while the proxy is paused.
- **The reference file stays on `.73:/mnt/HDD/kld/`** (about 5.1 GB) and is not committed.

**Scorer:** `tools/score_exl3_kld.py`, committed with this prereg.
