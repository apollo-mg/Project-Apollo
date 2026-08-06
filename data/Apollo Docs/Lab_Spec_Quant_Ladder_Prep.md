# Lab Spec: Quant Ladder — Prep Phase (Gemini task)

**For:** Gemini (executor). **Spec:** Fable (Architect). **Owner:** Mark. **Date:** 2026-07-13.
**Rig:** 4× Tesla P100, node `.194`. **Build:** `~/llama_stock/build_carveout` (stock 9967
`4f37f5197`, sm_60 carve-out — fp32-clean arithmetic). **Receipts dir:** `~/quant_ladder/` (create).

## ⚠️ EXECUTION LOCATION — READ THIS FIRST (fixes the Phase-0 preflight failures)
You (Gemini) run on `mark-desktop-pc` (the AMD RX 9070 XT box). It has **no `nvidia-smi` and no
`~/llama_stock`** — that is EXPECTED, not a failure. **ALL commands in this spec execute on the
P100 rig `.194` (`ai-supermicro-server`), reached via SSH:** `ssh mark@10.0.0.194 '<command>'`.
The build, the GPUs, and the canonical model directory all live on `.194`. The desktop's local
copy of `/home/mark/AI/Models/Qwen 3.6/27B/` is a stale artifact from an earlier download — IGNORE
it; do everything on `.194`. Every `df`/`nvidia-smi`/`stat`/`llama-perplexity`/`aria2c` below is
implicitly `ssh mark@10.0.0.194 '...'`. All paths (`~/quant_ladder`, the model dir) are `.194` paths.

## Purpose
Build the definitive Qwen3.6-27B quant-quality ladder: every tier scored against a **true
full-precision (BF16) base**, not the Q8 near-truth we've used so far. This PREP phase does the
mechanical bulk (downloads, byte-verify, base generation, tensor inventories). Scoring is a
separate follow-up. Everything here is self-verifying — every step ends in a disk check.

## ⚠️ Reporting rules (the Ground Truth Gate is in force — see GEMINI.md)
- **Every "I did X" carries its receipt in the same message.** A download claim needs the
  `stat -c%s` output next to it; a "base generated" claim needs the `ls -l` of the `.kld`.
- **No number you did not measure.** Byte counts come from `stat`, not from this spec restated.
- **Write only to `~/quant_ladder/` and the model dir — nothing to your private brain store.**
- **Two failures on any step → STOP and report verbatim.** Do not improvise a third variant.
- **Report format:** for each phase, a table of `item | expected bytes | actual bytes (stat) |
  PASS/FAIL | receipt path`. Nothing marked done without the stat/ls line pasted.

## Phase 0 — Preflight (report before downloading)
```bash
df -h /home                     # need ~120GB headroom (BF16 ~54GB + 3 quant tiers ~50GB + base ~16GB)
nvidia-smi                      # confirm idle, ~0 MiB
~/llama_stock/build_carveout/bin/llama-perplexity --version   # must print 4f37f5197
ls -l "/home/mark/AI/Models/Qwen 3.6/27B/"                    # what we already have
```
We ALREADY have (do not re-download): unsloth `Qwen3.6-27B-Q4_K_M.gguf` (16,817,244,384) and
`Qwen3.6-27B-Q8_0.gguf` (28,595,763,424). Quarantined static copies live in `lmstudio_static/` —
leave them.

## Phase 1 — Download missing tiers (all from unsloth/Qwen3.6-27B-GGUF for consistency)
FIRST fetch exact sizes from the HF API and save them, THEN download, THEN byte-verify:
```bash
curl -s https://huggingface.co/api/models/unsloth/Qwen3.6-27B-GGUF/tree/main \
  | python3 -m json.tool | tee ~/quant_ladder/hf_api_tree.json
```
Download (aria2c, `--allow-overwrite=true --auto-file-renaming=false`), byte-verify each with
`stat -c%s` == API size, log to `~/quant_ladder/download_verify.log`. **Confirmed filenames + exact
bytes (Architect-verified via HF API 2026-07-13):**
1. `BF16/Qwen3.6-27B-BF16-00001-of-00002.gguf` → **50,004,497,824** (BF16 is a subdir; note the `BF16/` prefix in the resolve URL)
2. `BF16/Qwen3.6-27B-BF16-00002-of-00002.gguf` → **3,803,783,936**  (BF16 = full-precision truth reference, ~53.8GB total)
3. `Qwen3.6-27B-Q3_K_M.gguf` → get exact bytes from `hf_api_tree.json`
4. `Qwen3.6-27B-Q5_K_M.gguf` → get exact bytes from `hf_api_tree.json`
5. `Qwen3.6-27B-Q6_K.gguf` → get exact bytes from `hf_api_tree.json`
Download all into `.194:/home/mark/AI/Models/Qwen 3.6/27B/` (place the two BF16 shards there too,
flattened — no `BF16/` subdir on disk). If any exact filename is absent, STOP and report the actual
available filenames — do not substitute a different quant silently.

## Phase 2 — BF16 truth base (the reference for the whole ladder)
```bash
~/llama_stock/build_carveout/bin/llama-perplexity \
  -m "/home/mark/AI/Models/Qwen 3.6/27B/Qwen3.6-27B-BF16-00001-of-00002.gguf" -f ~/wikitext-2-raw/wiki.test.raw -c 2048 --chunks 32 \
  -ctk f32 -ctv f32 -fa off -ngl 99 -ub 128 -ts 1,1,1,1 \
  --kl-divergence-base ~/quant_ladder/qwen27b_bf16_truth_f32kv_faoff_2k32.kld \
  2>&1 | tee ~/quant_ladder/truthbase_bf16.log
```
Corpus md5 MUST be `7c0137fc034ddbc56a296bce31b4f7fb` (verify + log). BF16 27B ≈ 54GB — if it
OOMs at `-ngl 99` on the 65GB quad, drop to partial offload (`-ngl 55 -ts 1,1,1,1`, raise/lower
to fit) — GPU layers are fp32-clean on this build, so partial offload does not corrupt the truth.
When done: record `.kld` size + md5 in `~/quant_ladder/truthbase_receipt.txt`, and note the base
PPL from the log (sanity: should be near Qwen's ~6.5).

## Phase 3 — Tensor inventory (what's actually in each tier)
For BF16, Q3_K_M, Q4_K_M, Q5_K_M, Q6_K, Q8_0 dump the tensor-type histogram (venv gguf reader,
method already proven — `~/venv/bin/python3`, `from gguf import GGUFReader`, Counter over
`r.tensors` `.tensor_type.name`). Save one table per model to
`~/quant_ladder/tensor_inventory_<tier>.txt`. Also record each file's total GiB. This exposes
which tiers are dynamic vs uniform (like the unsloth-vs-lmstudio Q4 finding).

## Deliverable back to Architect
One manifest: every downloaded file (path, expected bytes, stat bytes, PASS), the truth-base
receipt (size + md5 + PPL), and the six tensor-inventory tables. Each line carries its receipt
path. When this lands and is verified, the Architect runs the scoring cells (Q3/Q4/Q5/Q6/Q8 vs
the BF16 base) — the actual ladder chart.

## NOT in scope (do not do)
No scoring runs yet (Architect runs those). No IQ-quant tiers this pass (K-quants + Q8 + BF16
first, clean). No serving, no benchmarks, no llama-cli (banned — interactive spew). No deletions.
