# Lab Spec: Puzzle-75B APEX ladder — is the parallel-tool-call collapse a quant effect?

**Spec:** Claude (Architect). **Owner:** Mark. **Date:** 2026-08-02.
**Rigs:** `.194` 4× Tesla P100 (i-quality, i-compact) · `.73` 2× Tesla P100 (i-mini).
**Build:** `~/llama_stock/build_puzzle` on `.194` — branch `puzzle-port-p100` @ `73a55486c`,
**the same binary that produced BFCL leg W3**. Carries `n_expert_used_arr` (per-layer top-k), so
it loads Puzzle where the turboquant fork cannot.
**Receipts dir:** `data/receipts/bfcl-apex/`.

## The open question this closes

`data/receipts/bfcl/summary.txt` (leg W3, closed 2026-07-21) found:

| category | Puzzle-75B UD-IQ4-XL | Qwen3.6-27B Q8 |
|---|---|---|
| `multiple` | 31/35 = 88.6% | 31/35 = 88.6% — exact tie |
| **`parallel`** | **3/35 = 8.6%** | 32/35 = 91.4% |
| **`parallel_multiple`** | **3/35 = 8.6%** | 28/35 = 80.0% |

The **entire** 30pp overall gap is the parallel family. 32/35 failures are
`parallel_function_checker_no_order:wrong_count` — Puzzle emits **one** call where **N** are
required. Ruled out as a token-budget artifact (failing items produced 70–416 tokens, median 162).

That receipt states the open question verbatim: *"is the parallel collapse a QUANT effect
(UD-IQ4-XL) or an architectural/training property of Puzzle? … the clean test is a higher-quant
Puzzle control (Q5/Q6) on the parallel categories — proposed, not yet run."*

`Myric/Nemotron-Labs-3-Puzzle-75B-A9B-APEX-GGUF` supplies that control, and better: **three tiers
from one imatrix**, so bits-per-weight can be varied with calibration held constant.

| tier | size | bpw | rig | fits VRAM? |
|---|---|---|---|---|
| i-mini | 31.0 GB (28.9 GiB) | 2.94 | `.73` (31.8 GiB usable) | ~2.9 GiB headroom — tight, may need turbo3 KV or small `-c` |
| i-compact | 39.3 GB | 3.96 | `.194` | yes |
| **i-quality** | **49.9 GB** | **5.30** | `.194` (63.5 GiB) | yes, fully GPU-resident |

## Design — run i-quality FIRST, then decide

**i-quality alone is decisive.** If `parallel` jumps from 8.6%, the collapse is quant-sensitive
and the middle/low tiers locate the threshold. If it stays at ~8.6% with 5.30 bpw and a
tool-calling-aware imatrix, the collapse is architectural and the lower rungs add nothing.
Do not download/run i-compact or i-mini until i-quality reports.

**Matched conditions (both already verified):**
- **Same items** — reuse `data/receipts/bfcl/subset_ids_used.json` (`parallel` 35,
  `parallel_multiple` 35). Do **not** re-run `build_bfcl_subset.py`'s RNG.
- **Same harness** — `bfcl-eval==2026.3.23`. **A run on any other version is not a matched
  comparison.** ⚠️ **This harness cannot be built from `.194`'s system Python — see below.**

### ⚠️ Rebuilding the matched harness (CORRECTED 2026-08-03 — the old note was wrong)

An earlier draft said leg W3's venv "has lost its site-packages." That is not what happened:
**`.194` was upgraded to Ubuntu 26.04, whose only Python is 3.14.** Both `~/bfcl_venv` and
`~/bfcl_eval_venv` now report `Python 3.14.4`; the interpreter moved out from under them.
`~/bfcl_eval_venv` additionally holds **2025.8.6.2**, an *older* pin — do not use it.

`bfcl-eval==2026.3.23` hard-pins `faiss-cpu==1.11.0`, which has **no cp314 wheel**, so
`python3 -m venv` + `pip install` fails outright on this box:

```
ERROR: Could not find a version that satisfies the requirement faiss-cpu==1.11.0 (from bfcl-eval)
       (from versions: 1.12.0, 1.13.0, 1.13.1, 1.13.2, 1.14.2, 1.14.3)
```

**Do not "fix" this by relaxing the pin or by using the 2025.8.6.2 venv sitting right there.**
Different bfcl-eval versions ship different test data *and* a different scorer. Get 3.11 instead —
`uv` is installed at `/snap/bin/uv` and fetches a standalone interpreter without touching the system
(~68 s end to end):

```bash
export PATH=/snap/bin:$PATH
V=/home/mark/bfcl_w3_venv
uv python install 3.11
rm -rf "$V" && uv venv --python 3.11 "$V"
VIRTUAL_ENV="$V" uv pip install "bfcl-eval==2026.3.23"
VIRTUAL_ENV="$V" uv pip install pip     # see gotcha below
```

**Gotcha:** `uv venv` does **not** seed `pip`. `ds4_bfcl_chain.sh` gates on
`$VENV/bin/pip show bfcl-eval`, which returns an empty string without it — the chain then aborts
with `harness is , leg W3 used 2026.3.23`, which reads like a version mismatch and is not one.

**Verify before running anything:**

```bash
$V/bin/python --version                      # Python 3.11.x
$V/bin/pip show bfcl-eval | head -2          # Version: 2026.3.23
$V/bin/python -c "import faiss;print(faiss.__version__)"   # 1.11.0
```

Confirmed working 2026-08-03: Python 3.11.15, bfcl-eval 2026.3.23, faiss 1.11.0.
- **Same engine** — `~/llama_stock/build_puzzle`, the leg-W3 binary.
- Temperature 0, `OpenAICompletionsHandler`, `is_fc_model=True`, `underscore_to_dot=True`.

## ⚠️ The confound that limits interpretation — state it in the receipt

**CORRECTED 2026-08-02 after reading the GGUF metadata.** The earlier draft of this spec said the
confound was "imatrix vs none". That is wrong — leg W3's UD-IQ4-XL **already had an imatrix**:

```
quantize.imatrix.file          = /home/yaniss/models/puzzle-75b-gguf/puzzle-imatrix.gguf
quantize.imatrix.dataset       = /home/yaniss/hermes-work/hy3-port/calibration_datav3.txt
quantize.imatrix.entries_count = 392
```

(`/home/yaniss/` — quantized by **YanissAmz**, the author of upstream PR #25444.) APEX also
reports 392 entries, so both have full per-tensor coverage; what differs is the **corpus**:
standard `calibration_datav3.txt` vs APEX's corpus that explicitly includes tool-calling.

So the real confound between i-quality and UD-IQ4-XL is **bpw + calibration *corpus***, and a
tool-call-aware corpus remains a live alternative explanation for any improvement.

**Remy's quants resolve this**, because
`RemySkye/NVIDIA-Nemotron-Labs-3-Puzzle-75B-A9B-GGUF` states *"No importance matrix was used for
any quantization in this repository."* That gives a genuine third arm:

| bpw band | **no imatrix** (Remy) | **standard corpus** (Yaniss) | **tool-aware corpus** (APEX) |
|---|---|---|---|
| ~2.9–3 | Q2_K 31.5 GB — **on disk** | — | i-mini 31.0 GB |
| ~4 | IQ4_XS 43.0 GB | **UD-IQ4-XL 44.7 GB — on disk, 8.6%** | i-compact 39.3 GB |
| ~5.3 | **Q4_1 49.3 GB** | — | **i-quality 49.9 GB — downloaded** |

**Q4_1 (49.3 GB) vs i-quality (49.9 GB) is the cleanest single comparison available** — within
1.2% on size, i.e. near-identical bpw, differing *only* in calibration. Run that pair before
building the full ladder. Any receipt claiming "higher bits fixed it" from a single cross-corpus
point is wrong and must not be written.

## Known runtime characteristics (expected, not defects)

- **CUDA graphs are disabled for Puzzle on our fleet, unavoidably.** `ggml-cuda.cu:2588`
  `ggml_cuda_graph_check_compability` refuses graphs when `node->ne[2] > mmvq_mmid_max`.
  `MMVQ_MAX_BATCH_SIZE` is 8 and sm_60 uses the lowest table
  (`get_mmvq_mmid_max_batch_pascal_older`, 4–6 per type). Puzzle's per-layer top-k reaches **18**,
  so no quant type avoids it. The model card reports 6.5–9 t/s decode from this cause; expect
  slower on P100. **Affects speed only, not numerics** — and leg W3 ran under the same condition,
  so the comparison stays matched.
- BFCL outputs are short (median 162 tokens on failing items), so the run is **prefill-bound**,
  not decode-bound. ~70 items ≈ tolerable even at single-digit t/s.

## Phases

**Phase 1 — i-quality on `.194`.** Load on `build_puzzle`, confirm `n_expert_used_arr` accepted
(the turboquant fork fails here with `expert_used_count` arr-vs-u32). Run the 70 items. Report
per-category accuracy + the `wrong_count` failure breakdown (is it still emitting 1 call for N?).

**Phase 2 — only if Phase 1 moves the number.** i-compact on `.194`, i-mini on `.73`, same 70
items, same harness. Three points at 2.94 / 3.96 / 5.30 bpw, one imatrix → the bpw curve.

**Phase 3 (optional, `.73`).** i-mini VRAM-fit characterisation: does 28.9 GiB + KV fit in
31.8 GiB, and what does it cost (turbo3 KV, reduced `-c`, or partial offload)? This is a
TurboQuant receipt in its own right — a 75B frontier-distilled model on 32 GB of 2016 hardware.
⚠️ `.73` currently serves Qwopus3.6-27B on port 8082 (idle 24 h, ~19 GB VRAM). **Ask before
killing it** — `profiles.yaml` may route to it.

## Prediction (log before running)

- **P-A1** (confidence 0.65): i-quality does **not** restore parallel calling; `parallel` stays
  below 25%. Reasoning: leg W3's token-level analysis "leaned against pure-quant", the failure is
  a *multiplicity* error rather than a schema/syntax error, and multiplicity looks like a
  learned-behaviour property. A quant artifact would more plausibly corrupt call *structure*.
- **P-A2** (0.55): if i-quality *does* improve it, the imatrix (not bpw) is the cause — i.e. the
  within-APEX ladder will be **flat**, with all three tiers similar and all above UD-IQ4-XL.
- **P-A3** (0.8): `multiple` stays ~88% on every APEX tier (it was never the problem).

## Related unfinished business — Puzzle **with** MTP (separate leg, not this spec)

`~/llama_stock` branch `puzzle-port-p100` contains **MTP support that upstream PR #25444 does not**
— the author stripped it for review ("will come back as a separate follow-up PR"):
`9a257fc60` (convert: NemotronHPuzzle per-block MoE config **+ MTP head**), `c097d55bf`
(NEXTN/MTP for NEMOTRON_H_MOE), `ddafe470c`, `af49ef5cd`. All four are ancestors of the built HEAD.

So the APEX card's *"MTP draft head is dropped during conversion … no inference support exists
upstream"* is true of **upstream**, not of our tree.

### ⚠️ CORRECTION — no conversion is needed. The MTP head is already on disk.

The earlier draft said this leg needed a ~157 GB BF16 download plus conversion. **Wrong.** Both
Puzzle GGUFs already on `.194` carry the MTP tensors:

```
nemotron_h_moe.nextn_predict_layers = 2
blk.88.nextn.eh_proj.weight   blk.88.nextn.enorm.weight   blk.88.nextn.hnorm.weight
blk.89.nextn.shared_head_norm.weight
```

— present in **both** `Puzzle-75B-A9B-UD-IQ4-XL.gguf` (44.7 GB) and Remy's `Q2_K` (31.5 GB).
And `build_puzzle`'s `llama-server` exposes `--spec-type … draft-mtp …` plus
`--spec-draft-n-max N` (the parameter behind Chris's n-max sweep in #249).

**So Puzzle-75B MTP speculative decoding is runnable today, zero downloads.** That makes it the
cheapest high-value leg in the queue, not the most expensive. The #249 thread established that
fork-MTP's fixed per-round overhead (~7 ms/cycle) is net-negative on a 5090 (225 → 112.7 t/s) and
positive only on bandwidth-poor hardware. Pascal at ~200 ms/step is the extreme end of that axis
— where MTP should look *best*, and where nobody in the thread has hardware.

Design when run: A/B `--spec-type none` vs `draft-mtp` at matched settings, K≥3 per arm with the
warm/cold discipline from `DS4_DECODE_WARMUP.md`, sweeping `--spec-draft-n-max` 1–4 to match
Chris's protocol. Report acceptance rate alongside t/s — high acceptance with collapsed
throughput is the per-call-overhead signature.

⚠️ Note: the sm_60 FAST_FP16 fix lives on a **separate** branch (`sm60-fp32-carveout`), so
`build_puzzle` does **not** contain it. Fine for matching leg W3; do not mix new Puzzle numbers
with post-fix results.
