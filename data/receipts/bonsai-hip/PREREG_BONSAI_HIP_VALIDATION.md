# Pre-registration -- is Bonsai 2 PQ2_0 decoded correctly on HIP (RX 9070 XT, gfx1201)?

**2026-09-25, before any HIP Bonsai forward pass.** An instrument validation, not an experiment. Its purpose is to
decide whether any Bonsai judgement measured on the 9070 can be trusted.

buun's own `docs/bonsai.md` (`ecfeb94fb`) says: "HIP shares fallback code but has not been hardware-validated
here." The prism fork makes no HIP claim at all.

**Prior art checked:** `ledger_precheck.py "Bonsai ternary PQ2_0 HIP ROCm gfx1201 perplexity validation"` -> receipts
found:
- `atlas-gfx1201/FINDING_TERNARY_Q2_0.md`: Atlas has Q2_0 kernels for gfx1201; that is a different codebase.
- `battle16gb/HA20_BONSAI_VS_GEMMA.md`: Bonsai **v1** (Q2_0) on the 9070 via a July upstream branch.
- `agentic-ladder/RESULT_PA0_GATE.md`: Bonsai 2 PQ2_0 KLD 0.358 against Qwen3.8-27B, measured on .194.

None of these validates PQ2_0 (Prism wire type 142) on HIP in buun or prism.

## Instrument

- **Model:** `Ternary-Bonsai-2-27B-PQ2_0.gguf`, sha256 `3907dc1658db1f78...`, the same file on both nodes.
- **Text:** `wiki.test.raw`, sha256 `f36668ddf2240...`, the same bytes on both nodes. .194's own copy differs and is
  not used.
- **Settings:** `llama-perplexity -c 512 -b 512 --chunks 10`, f16 KV (`-ctk f16 -ctv f16`), `-ngl 99`.
- **Reference:** .194, prism `9a9394a` sm_60 CUDA, GPUs 0,1 `-sm layer`, `GGML_CUDA_ALLREDUCE=internal`. This is the
  implementation that produced the marker-penalty rows. It writes `--kl-divergence-base`.
- **Arms on the 9070**, each run with `--kl-divergence` against that base:
  - **H1:** buun `38ada0e1b` `build_rocm` (PQ2_0 remapped to `Q2_0_G128`);
  - **H2:** prism `9a9394a` `build_hip` (worktree `engines/prism_sep`).

## Pass bar (set now)

**PASS** requires every one of these:
- mean KLD vs the CUDA reference **<= 0.01**;
- same-top-token **>= 95 %**;
- final PPL within **2 %** of the reference.

**FAIL** is any of: mean KLD > 0.05; same-top < 90 %; PPL off by more than 5 %; NaN or inf.
Anything in between is **SUSPECT**, and the arm is not used for judgement work until it is explained.

**Why these numbers.**
- Bonsai 2's own quantization damage relative to Qwen3.8 is KLD 0.358, so a broken kernel lands far above 0.05.
- Legitimate cross-backend noise on Pascal was median KLD 0.0023 with same-top 96.5 %, before the FAST_FP16 fix
  (`pascal-kv-finding`). The prism sm_60 reference may or may not carry that fix, so the bar leaves room for it.

**Control:** H1 vs H2 is computed descriptively from their PPL and top-token agreement with the reference. If both
HIP arms agree with each other but miss the CUDA reference by the same amount, suspect the reference's Pascal path
before the HIP code.

**Load probe (must hold before scoring):** each log must report the ternary tensors under the expected type (PQ2_0 /
Q2_0_G128), print a final PPL estimate, and show no NaN. `llama-perplexity` exits 0 on failure, so the exit code
proves nothing.

## Deviation 1 (21:25, before any forward pass completed): the eval text

The registered text (sha256 `f36668ddf2240...`) is `data/wikitext/wiki.test.raw` in this repo. It is **15 bytes: a
saved Hugging Face "Entry not found" page**, and the reference run refused it at tokenization ("tokenizes to only 3
tokens"). The same directory's `wikitext-2-raw-v1.zip` is 0 bytes. Both have been stubs since 2026-03-30.

The text is now the real WikiText-2 test file from .194: `~/wikitext-2-raw/wiki.test.raw`, 1,290,590 bytes, sha256
`173c87a53759e020...`. A byte-identical copy is used on the 9070. Nothing else changes.
