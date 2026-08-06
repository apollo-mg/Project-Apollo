# MTP speculative decoding on Pascal (sm_60): 1.70× throughput, but NOT bit-exact

**Date:** 2026-07-26 · **Node:** `.73` dual Tesla P100-PCIE-16GB (sm_60), **1063 MHz / 150 W** on
both cards, verified before and after · **Build:** `~/buun_vbr/build/bin/llama-server`
**Model:** `DavidAU-Fable-Fusion-711-MTP-Q6_K.gguf` — carries `qwen35.nextn_predict_layers = 1`

## Result

| arm | aggregate tok/s | per-prompt spread |
|---|---|---|
| **MTP on** (`--spec-type draft-mtp --spec-draft-n-max 2`) | **20.23** | 19.41 – 21.45 |
| **MTP off** | **11.87** | 11.85 – 11.90 |
| MTP off, repeat | 11.89 | 11.85 – 11.91 |

**Speedup: 1.70×.** 5 prompts × 512 output tokens each (all `finish=length`, so token counts
are identical across arms and tok/s is directly comparable).

The off arm's spread is nearly flat (11.85–11.90) — pure autoregressive decode. The on arm
varies 10× more (19.41–21.45) because throughput now depends on draft acceptance, which is
content-dependent. That spread is itself evidence the mechanism is live.

## The exactness finding, and the control that makes it a finding

At temp 0 / top_k 1 / fixed seed, **MTP-on and MTP-off produce different output on 4 of 5
prompts.** Divergence is not immediate — the two arms agree for ~500–1500 characters of
reasoning before splitting, consistent with slow numerical drift flipping an argmax rather
than a gross algorithmic difference.

That claim only means something with a determinism control, because llama.cpp/CUDA results
depend on batch shape and **speculative decoding changes batch shape by construction** —
verifying k drafted tokens in one pass is not the same arithmetic as k single-token passes.

**Control: MTP-off run 1 vs run 2, identical config → 5/5 byte-identical.**

So this stack *is* reproducible run-to-run at temp 0, and the 4/5 divergence **is
attributable to MTP**, not to background non-determinism.

| comparison | byte-identical |
|---|---|
| MTP-off vs MTP-off (control) | **5/5** |
| MTP-on vs MTP-off (treatment) | **1/5** |

### What this does and does not say

- It **does** say: enabling MTP changes what the model emits, measurably, on this build.
- It does **not** say MTP is worse. Output quality was not measured — only that it differs.
  A pass@1 comparison would be needed to claim any accuracy effect.
- Textbook speculative decoding is distribution-exact by construction (the target verifies
  every drafted token). The most likely mechanism here is therefore **numerical**, from the
  batch-shape change, not a broken accept/reject rule. That is an inference, not a
  measurement — confirming it would need logit-level comparison.

## Practical consequences

1. **MTP is a serving win, not a benchmarking tool.** 1.70× for free on interactive work is
   excellent. For a benchmark whose numbers get published, it perturbs the thing being
   measured.
2. **Never enable MTP on one arm of an A/B.** The original stage-2 queue did exactly this by
   accident — ThinkingCap pointed at an MTP GGUF, stock at a non-MTP one. Inert while the
   flag was off; a confound the moment it is switched on.
3. Enabling it on **both** arms keeps an A/B internally valid but breaks comparability with
   any non-MTP receipt — including `data/receipts/humaneval-plus/`.
4. **Puzzle-75B is MTP-capable and nobody had noticed:** its GGUF already carries
   `nemotron_h_moe.nextn_predict_layers = 2`, and the build has a `mtp_on_hybrid_nemotron_h`
   branch written specifically so draft rollback works with its non-recurrent MTP sub-blocks.
   The 10-hour HumanEval+ leg may be repeatable in ~6 h — at the cost of exactness above.

## Method notes

- Both arms were launched from the **captured argv of the live server**
  (`argv_mtp_on.txt`, read from `/proc/<pid>/cmdline`), with only `--spec-type` and
  `--spec-draft-n-max` removed for the off arm. Every other flag — buun's VBR KV cache
  (`-ctk vbr -ctv vbr --vbr-floor 6.125`), `-fa on`, `-np 2`, `-sm tensor -ts .85,1.15`,
  `-c 260000`, the chat-template-kwargs JSON — is byte-identical between arms. Nothing was
  retyped.
- Server restored to the original MTP-on recipe afterwards; verified by re-reading cmdline.

## Scope limits

- One model, one build, one quant (Q6_K), 5 prompts, 512 tokens each.
- `--spec-draft-n-max 2` with 1 nextn layer — a deliberately modest draft depth. Higher
  n-max may change both the speedup and the divergence rate; untested.
- Throughput measured with `-np 2` and a 260k context allocated. Not a clean single-slot
  number.
- Generalization to sm_60 broadly is untested: this is one Pascal pair, and the KV cache is
  buun's VBR rather than stock.

## Files

| file | what |
|---|---|
| `arm_mtp_on.json` / `arm_mtp_off.json` | per-prompt timings + full output text |
| `arm_mtp_off_rep2.json` | the determinism control |
| `argv_mtp_on.txt` | exact captured server argv |
| `mtp_ab.py` | benchmark harness |
| `relaunch_73.py` | argv-preserving relaunch (on/off) |
| `mtp_control.py` / `mtp_compare.py` | analysis |
| `gguf_kv.py` | GGUF header KV reader (used to find `nextn_predict_layers`) |
