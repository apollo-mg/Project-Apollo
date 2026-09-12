# Prereg — what the freed 8 GB buys at long context (EXL3 campaign, test 5, ledger O4 and O7)

**Written 2026-09-12 ~16:35, before any long-context data.** **Not launched without Mark's go-ahead:** it
holds `.73` for about an hour and costs two dev-diary ledger runs.

## Question

At the daily driver's config, EXL3 leaves **8.1 GB more VRAM free** than the Q6_K (17.7 vs 25.8 GB
across both cards). VBR sizes its KV budget from what is left (`--vbr-vram auto`), and it degrades KV
precision under pressure, from an f16 entry tier down toward a 2.25 bits/value floor.

**So the freed VRAM should show up as a higher KV tier at long context** — the same context, held at
better precision. This test looks for that, and settles two open ledger items at once:
- **O4's degrade path,** which test 1 never exercised: every arm stayed at the f16 entry tier through
  14,852 tokens.
- **O7's long context,** untested so far.

## Setup

- **Node:** `.73`, both P100s, the wake proxy paused with a dead-man timer.
- **Binary:** QUAL (buun `9ae8f0f40` + e8m0 guard), the same as tests 1, 3 and 4.
- **Flags:** the daily driver's exact command, as in test 1 — MTP, the F16 mmproj, `-ctk vbr -ctv vbr
  --vbr-floor t2 --vbr-vram auto`, `-c 262144`, `-sm tensor -fit off`, on port 8190.
- **Arms:** **X** = EXL3 4.00bpw, **Q** = the daily driver's Q6_K.
- **Text:** wikitext-2-raw test, the same file as every other test in this campaign.

**Depths are reached once per arm, cumulatively.** The prompt is extended in place with
`cache_prompt: true`, so each arm prefills about 131k tokens in total rather than 212k:

| step | context depth | measured after it |
|---|---|---|
| 1 | ~16,384 tokens | `kv_bpv`, VRAM, decode t/s over 32 tokens |
| 2 | ~65,536 | the same |
| 3 | ~131,072 | the same |

`kv_bpv` and VRAM are read from `/slots` and `nvidia-smi` after each step, before the decode.

## Predictions

| id | prediction |
|---|---|
| P-L1 | **At 131k, X's `kv_bpv` is higher than Q's.** The freed VRAM buys KV precision |
| P-L2 | Both arms reach 131k and answer, with no OOM and no failed decode |
| P-L3 | At least one arm leaves the f16 entry tier by 131k (`kv_bpv` < 16). Otherwise this test again fails to exercise the degrade path, and P-L1 is **VOID** |
| P-L4 | X's total VRAM stays below Q's at every depth |
| P-L5 | The X÷Q decode ratio at 131k is within 10 points of the ratio at 16k. Depth does not change the speed story |

## Declared in advance

- **`kv_bpv` is VBR's own report of its tier, not a quality measurement.** A higher tier means less
  quantization of the KV cache; it does not by itself prove better answers. Measuring quality at depth
  would need a KLD run at depth, which this test does not do.
- **Decode at depth is measured over 32 tokens,** one rep per depth. It is an estimate.
- **The arms prefill the same token counts,** but EXL3 and Q6_K tokenize identically (same base model),
  so depth is comparable.
- **This costs two ledger runs** while the proxy is paused.
- **If an arm cannot reach 131k,** that is itself the result for O7, and it is reported rather than
  retried at a shorter depth.

**Driver, orchestrator and scorer** are written only once this test is greenlit, so that nothing
half-built sits in the repo.
