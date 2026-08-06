# Lab Brief: Puzzle-75B-A9B Model Eval + Dynamic-vs-Static Quant Panel

**For:** Gemini (executor). **Spec:** Claude (Architect). **Owner:** Mark.
**Date:** 2026-07-13. **Rig:** `.194`, 4× Tesla P100-PCIE-16GB (sm_60), 65GB total VRAM.
**Build:** `~/llama_stock/build_puzzle/` — branch `puzzle-port-p100`, `version: 9937 (73a55486c)`
(yaniss puzzle-port + the sm_60 FAST_FP16 carve-out cherry-picked — GPU arithmetic is fp32-clean).
**Receipts dir (create):** `~/puzzle_lab/` — every command's full output tees into a named log here.

## Two questions, in order

1. **Model eval:** is Puzzle-75B-A9B usable on quad P100 — tuned speed, real text quality?
2. **Quant panel:** does the dynamic mixed-precision quant (UD-IQ4-XL, 41.6 GiB) match or beat
   the static uniform quant (Q4_K_M, 48.05 GiB) against a shared Q8_0 truth base?
   **Framing discipline: these are NOT matched bytes (13% apart).** The honest claim shapes are
   "smaller dynamic hangs with / beats bigger uniform" or "dynamic loses even with the excuse of
   fewer bytes." Never report a winner without the byte counts next to it.

## Hard rules (violating any of these voids the run)

- **NEVER use `llama-cli` from this build.** It ignores `-no-cnv`, goes interactive on closed
  stdin, and spews `> ` at 2MB/s (produced a 5.4GB log on 07-12). Use `llama-bench`,
  `llama-perplexity`, or `llama-server` + `curl` only.
- Nothing else may be running on the P100s during any measured leg (`nvidia-smi` before each).
- **Delete nothing without listing it to Mark first and getting an explicit yes.** This includes
  "obviously safe" old downloads. Exception: files you yourself created in `~/puzzle_lab/` this session.
- Do not touch `~/carveout_panel/`, `~/moe_panel/`, `~/phaseb/`, `~/tom_validation/`,
  `~/qwen-base-logits-kld/` — those are published receipts.
- If a step fails twice, stop that phase and report — do not improvise workarounds.
- NVFP4 variant: **out of scope, do not download** (no evidence of sm_60 support; 48GB of curiosity).
- Log every result verbatim, including ones that look wrong. Wrong-looking numbers are findings.

## Phase 0 — Preflight (report before downloading anything)

```bash
df -h                      # all mounts — the staging decision below depends on this
free -g                    # RAM decides truth-base strategy (need ~90GB to hold Q8_0 in RAM)
nvidia-smi                 # confirm idle
~/llama_stock/build_puzzle/bin/llama-bench --version   # must say 9937 (73a55486c)
ls -l ~/AI/Models/Nemotron/Puzzle-75B/                 # Q4_K_M shards: 44,818,402,912 + 6,781,439,072 bytes
```

**Disk decision tree.** Needed: UD-IQ4-XL 44.7GB + Q8_0 83.5GB + truth base ~20GB ≈ 148GB peak
(Q8_0 is deletable after the truth base is verified, with Mark's yes — see Phase 3).
As of 07-12 `.194` had ~91GB free, which is NOT enough.
- If another local mount has room, stage Q8_0 there.
- Otherwise: inventory `~/AI/Models/` with sizes, report to Mark, and **stop until he approves
  moves/deletions.** Do not pick sacrifices yourself.

Pull exact byte sizes for the two downloads from the HF API and record them in
`~/puzzle_lab/expected_sizes.txt`:
```bash
curl -s https://huggingface.co/api/models/YanissAmz/Nemotron-3-Puzzle-75B-A9B-GGUF/tree/main | python3 -m json.tool | tee ~/puzzle_lab/hf_tree.json
```

## Phase 1 — Downloads + byte verification

Download `Puzzle-75B-A9B-UD-IQ4-XL.gguf`, both `Q8_0` shards, and `puzzle-imatrix.gguf` (221MB,
provenance receipt) using the same method that fetched Q4_K_M on 07-12. After each: `ls -l`,
compare against the HF API byte counts, log to `~/puzzle_lab/download_verify.log`. A size
mismatch = re-download, not a shrug.

## Phase 2 — Tensor inventory (what "UD…XL" actually is — receipts, not marketing)

Use the gguf python dump (in the venv on `.194`, or `gguf-dump` from the build tree) on BOTH
quants. For each, produce a histogram: tensor-type → count → total bytes, split by tensor-name
class (attention `attn_*`, expert FFN `ffn_*exps`, router/gate, embeddings/output, mamba/ssm
tensors). Save as `~/puzzle_lab/tensor_inventory_{q4km,udiq4xl}.txt`.

This answers Mark's open question of what the UD recipe actually upcasts on a hybrid
mamba/attention/MoE arch. Report the histogram — no interpretation needed from you.

## Phase 3 — Truth base (Q8_0, fp32 arithmetic, the step everyone skips)

Strategy by RAM (from Phase 0):
- **RAM ≥ ~90GB:** run CPU-only (`-ngl 0`) — pure fp32 CPU arithmetic, cleanest possible truth.
  Only ~9B params active per token; overnight is acceptable. Run under `nohup`/`tmux`.
- **RAM < 90GB:** partial offload — highest `-ngl` that fits alongside f32 KV (GPU layers are
  fp32-clean on this build thanks to the carve-out). Start conservative, e.g. `-ngl 40 -ts 1,1,1,1`,
  adjust on OOM.

```bash
# corpus: the exact wikitext-2 test file used in ~/carveout_panel runs
# (find path in those run logs; md5 MUST be 7c0137fc034ddbc56a296bce31b4f7fb — verify, log it)
~/llama_stock/build_puzzle/bin/llama-perplexity \
  -m <Q8_0 shard 1> \
  -f <wikitext-2-test> -c 2048 --chunks 32 \
  -ctk f32 -ctv f32 -fa off \
  --kl-divergence-base ~/puzzle_lab/puzzle75b_q8truth_f32kv_faoff_ctx2048_32ch.kld \
  2>&1 | tee ~/puzzle_lab/truthbase_gen.log
```

Expect the `.kld` base around ~20GB (scales with vocab). When done: record its size + md5 in
`~/puzzle_lab/truthbase_receipt.txt`, then **verify it is readable** by running one quick
`--kl-divergence` scoring pass (Phase 4 cell A counts). Only after that verification may the
Q8_0 shards be proposed for deletion — propose to Mark, wait for yes.

## Phase 4 — KLD panel (the quant comparison)

Both cells on quad P100, patched build, **f32 KV, FA off** — KV and attention config pinned so
the ONLY variable is weight quantization. Same corpus, ctx, chunks as the base.

```bash
# Cell A — static uniform
~/llama_stock/build_puzzle/bin/llama-perplexity \
  -m ~/AI/Models/Nemotron/Puzzle-75B/Puzzle-75B-A9B-Q4_K_M-00001-of-00002.gguf \
  -f <wikitext-2-test> -c 2048 --chunks 32 \
  -ctk f32 -ctv f32 -fa off -ngl 99 -ts 1,0.72,1.14,1.14 \
  --kl-divergence --kl-divergence-base ~/puzzle_lab/puzzle75b_q8truth_f32kv_faoff_ctx2048_32ch.kld \
  2>&1 | tee ~/puzzle_lab/kld_q4km.log

# Cell B — dynamic mixed (same command, UD-IQ4-XL path, tee kld_udiq4xl.log)
```

Notes:
- The `-ts 1,0.72,1.14,1.14` split was hand-tuned for Q4_K_M. UD-IQ4-XL has a different byte
  layout **and f32 KV is ~2× bigger than the f16 KV used at first light** — expect OOM on the
  first try in either cell. On OOM: reduce the pressure on whichever device
  `ggml_backend_cuda_buffer_type_alloc_buffer` names, in 0.05 steps. Log every attempted split.
  If f32 KV simply doesn't fit even after splits: fall back BOTH cells to `-ctk f16 -ctv f16`
  (still FA off), note it in the receipts, and regenerate nothing — the truth base stays f32.
- Record from each: median/mean/99.9%/max KLD, max Δp, same-top %. The FULL stat block, verbatim.

## Phase 5 — Speed panel

llama-bench, both quants, same flags, 3 repetitions, nothing else on the GPUs:

```bash
~/llama_stock/build_puzzle/bin/llama-bench \
  -m <model> -ngl 99 -ts 1/0.72/1.14/1.14 \
  -p 512 -n 32 -r 3 2>&1 | tee ~/puzzle_lab/bench_<quant>_pp512.log
# then a depth leg: -p 2048 -n 32 -d 4096 -r 3   → bench_<quant>_d4096.log
```

(First-light reference, Q4_K_M, 07-12: pp512 136.72±4.13, tg32 13.23±0.16. If Q4_K_M today
deviates >5% from that, something else is on the box — stop and check.)

Optional if time allows: `-ub 64,128,256` sweep on whichever quant won, pp512 only — the MoE
micro-batching trick from the RX 9070 XT recipe has never been tried on this model.

## Phase 6 — Real-text smoke (llama-server, NOT llama-cli)

```bash
~/llama_stock/build_puzzle/bin/llama-server -m <winner from Phase 4> \
  -ngl 99 -ts 1,0.72,1.14,1.14 -c 8192 --port 8091 2>&1 | tee ~/puzzle_lab/server_smoke.log &
# wait for ready, then 3 fixed probes via curl (temp 0.6, max 512 tokens each):
#  1. "Explain the difference between a mutex and a semaphore, with a code example."
#  2. "Summarize the plot of Moby-Dick in exactly three sentences."
#  3. "Write a Python function that merges two sorted lists in O(n)."
# save raw JSON responses to ~/puzzle_lab/smoke_{1,2,3}.json, then kill the server.
```

This is a sanity read (coherence, chat template health, obvious repetition loops), not a benchmark.
Note in passing whether the server logs mention the MTP draft head; do not chase it.

## Predictions (Claude, logged 2026-07-13 BEFORE any run — score me afterward)

1. **Quality: UD-IQ4-XL beats Q4_K_M on median KLD vs the Q8_0 truth base** despite 13% fewer
   bytes — the upcast attention/router tensors matter more on a MoE-routed hybrid than uniform
   expert precision. Confidence: moderate. (If it loses, dynamic-quant hype takes a real hit —
   it can't even win with fewer bytes as an excuse.)
2. **Speed: UD-IQ4-XL decodes SLOWER than Q4_K_M on P100** despite being smaller — i-quant
   dequant cost on sm_60 (no DP4A, emulated byte math) eats the bandwidth savings. Confidence:
   moderate-low; Pascal has burned me 7 times this arc.
3. Q4_K_M same-top vs Q8_0 truth lands in the 97–99% band (weight-quant effect on a NAS-pruned
   MoE is real but not catastrophic at 4-bit). Confidence: low — NAS-pruned models may be less
   quant-tolerant than their dense-trained cousins; a surprise here is itself a finding.

## Report format (what comes back to Mark)

One table: quant | GiB | median KLD | same-top % | pp512 t/s | tg32 t/s — plus the full stat
blocks and every receipt path. Predictions scored 1–3 with verdicts. Anomalies listed
separately, uninterpreted.
