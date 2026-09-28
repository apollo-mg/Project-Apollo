# Result -- MTP on Flash-Next under heavy expert offload: 1.30x on 2 GPUs, 1.44x on 4, well short of the 1.72x predicted. 75 % draft acceptance, 2.49 tokens per step.

**Run 2026-09-02 ~14:24-14:35 on .194; written up 2026-09-28 from the raw logs, which sat unscored for 26 days.**
Predictions: `PREDICTIONS_flashnext_mtp.md` (registered 09-02, before the run). Driver and raw output:
`flashnext_mtp_0902/` (`fn_mtp.sh`, `results.tsv`, per-arm `server.log` and `r1-3.json`; home paths redacted to `~`).

**Setup:**
- buun `~/buun-llama-cpp/build_sm60_qwen4` (the 09-02 tree, with the shared-sidecar support of `2d5ef7910`);
- `Qwen3.8-Flash-Next-UD-Q2_K_XL` plus the shared MTP sidecar `mtp-Qwen3.8-Flash-Next-shared-Q8_0.gguf` (68 KB; it
  reuses the target's tensors);
- `-c 8192 -fa on -np 1 -fit off -sm tensor -ngl 99 -ncmoe 44` (44 of 48 MoE layers' experts on the CPU),
  `--draft-max 3`;
- 3 reps of one prompt per arm, with a coherence check ("paris"). P100s at the fleet cap (150 W, 1063 MHz).

## Results

| devices | MTP off (tok/s, 3 reps) | MTP on | speedup (median) | draft acceptance |
|---|---|---|---:|---|
| 2 | 7.38 / 7.91 / 7.91 | 9.87 / 10.30 / 10.42 | **1.30x** | 0.752 (76/101), mean 2.49 tokens/step |
| 4 | 5.59 / 5.82 / 5.82 | 7.88 / 8.36 / 8.30 | **1.44x** | 0.745 (76/102), mean 2.49 tokens/step |

| # | prediction (09-02) | result |
|---|---|---|
| P1 | MTP speedup at 2 devices beats the 27B's 1.72x | **false** (1.30x) |
| P2 | above 2.0x | **false** |
| P3 | 4 devices stay slower than 2 even with MTP | **holds** (8.30 < 10.30) |
| P4 | the sidecar loads and MTP engages | **holds** |

**The registered falsifier fired.** "If MTP gives less than 1.72x here, the 'fixed expert-fetch cost amortises across
drafted tokens' model is wrong and the bottleneck is something that scales with drafted tokens too." Under heavy
offload, verifying a 3-token draft is not close to free: routed experts differ per drafted token, so the expert
reads from host memory grow with the draft.

## Limits and what came after

- One prompt, 3 reps. Acceptance comes from one short answer.
- **`-sm tensor` is disabled upstream for qwen4exp** since this run (#27941), so the 2 vs 4-device comparison is
  historical.
- The open question it leaves: **MTP with the model fully GPU-resident** (Q2, `-ngl 99`, layer split, 21 tok/s
  without MTP per `RESULT_FLASHNEXT_RESIDENCY.md`). There the expert reads come from HBM, not host memory. That, and
  whether the P100 clock pin (BACKLOG N11) costs the verify step more than plain decoding, is the next preregistration.
- For scale: a public vLLM recipe on one DGX Spark reports ~3.7 tokens/step with this model's MTP head (W4A16
  experts). That is a different engine, quant and hardware, cited only as an upper reference, not a comparison.
