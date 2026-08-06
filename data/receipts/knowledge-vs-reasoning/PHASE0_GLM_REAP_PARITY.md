# Phase 0 — GLM-4.7-Flash REAP pair: gates G-1 and G-4

**Date:** 2026-08-06. **Spec:** `Lab_Spec_Knowledge_vs_Reasoning_Under_Compression.md`.
**Verdict:** G-1 **passes**, G-4 **measured**, with one fragile dependency that must be re-checked on
the runtime binary before any measurement.

## Arms

| arm | file | bytes |
|---|---|---|
| base | `GLM-4.7-Flash-Q6_K.gguf` | 24,693,098,848 |
| pruned | `GLM-4.7-Flash-REAP-23B-A3B-Q6_K.gguf` | 18,989,367,008 |

Both on `.73` at `/mnt/models/AI_Models/GLM/4.7 Flash/`. Sizes match the HF listing exactly.
Plain `Q6_K`, deliberately **not** the `UD-` variants (Unsloth Dynamic does per-tensor type selection
driven by each model's own characteristics, which would place recipe divergence inside the pruning
delta).

Method: header-only GGUF read, stdlib solely (`gguf_probe.py`, `gguf_kvdiff.py` alongside this file).
`.73` has neither numpy nor a venv; nothing was installed on it. Tensor data was never read.

## G-1 — packaging parity: PASS

| property | base | REAP |
|---|---|---|
| tensor count | 844 | 844 |
| type histogram | Q6_K 376 / F32 281 / Q8_0 187 | **identical** |
| `general.file_type` | 18 | 18 |
| `general.quantization_version` | 2 | 2 |
| `quantize.imatrix.chunks_count` | 85 | 85 |
| `quantize.imatrix.entries_count` | 607 | 607 |
| `quantize.imatrix.dataset` | `unsloth_calibration_GLM-4.7-Flash.txt` | `unsloth_calibration_GLM-4.7-Flash-REAP-23B-A3B.txt` |

The per-tensor recipe is **identical**, which is what the gate is about. The imatrix *files* necessarily
differ — an imatrix is activation statistics from the specific model and cannot be shared — and the
matching `chunks_count` (85) and `entries_count` (607) are good evidence the same calibration corpus
was used on both.

## G-4 — prune ratio: measured, and it agrees with the card

| | base | REAP |
|---|---|---|
| `deepseek2.expert_count` | **64** | **48** |
| expert tensor shape (`blk.1.ffn_up_exps.weight`) | `[2048, 1536, 64]` | `[2048, 1536, 48]` |
| `deepseek2.block_count` | 47 | 47 |

**16 of 64 experts removed — a 25% prune.** The REAP file's own `general.description` states
*"uniformly pruning 25% of experts in GLM-4.7-Flash using the REAP method"*, which matches the
measurement. Layer count is unchanged, so experts are the only structural variable.

Architecture, for the record: `general.architecture = deepseek2` (GLM-4.7-Flash runs llama.cpp's
DeepSeek2 path), `expert_used_count = 4` (top-4), `expert_shared_count = 1`,
`leading_dense_block_count = 1`, `general.size_label = 64x2.6B`.

**Design consequence.** This is a far coarser prune than the Qwen3.6 REAP (51 of 256). At 64 experts
with top-4 routing, each expert carries much more of the model, so a 25% cut should produce a
*larger* effect and an easier detection. Good for the experiment.

## ⚠️ The near-miss: `expert_gating_func` is absent from the REAP file

`gguf_kvdiff.py` found three keys present in the base and missing from the pruned arm:

```
deepseek2.expert_gating_func = 2          <-- 2 = SIGMOID
general.sampling.temp        = 1.0
general.sampling.top_p       = 0.95
```

Unsloth's own GLM-4.7-Flash guide states the **sigmoid** scoring function is required, not softmax.
A gating-function mismatch between arms would be a routing confound sitting **directly on the
mechanism under test** — expert routing is the thing REAP modifies.

It is saved by a hardcoded compatibility shim. `llama-model.cpp:1593-1601`:

```c
ml.get_key(LLM_KV_EXPERT_GATING_FUNC, hparams.expert_gating_func, false);   // optional
if (hparams.expert_gating_func == LLAMA_EXPERT_GATING_FUNC_TYPE_NONE) {
    if ((hparams.n_layer == 47 || hparams.n_layer == 48) && n_vocab == 154880) {
        hparams.expert_gating_func = LLAMA_EXPERT_GATING_FUNC_TYPE_SIGMOID;   // GLM 4.7 Lite
    } else {
        hparams.expert_gating_func = LLAMA_EXPERT_GATING_FUNC_TYPE_SOFTMAX;
    }
}
```

Both arms satisfy the shim **exactly**: `n_layer = 47`, `n_vocab = 154880` (measured on both).
So on mainline the REAP arm resolves to SIGMOID and the arms agree.

**Why this is only a conditional pass.** The match depends on a hardcoded heuristic, not on the file
saying what it means. On a fork whose deepseek2 branch lacks that shim — or on any build predating
it — the REAP arm silently becomes **softmax** while the base stays sigmoid, with no error and no
warning. Different routing on the arm whose routing we are measuring.

### G-1a — runtime verification: PASS

Per §1 the source is not evidence about which path ran, so both arms were loaded on the binary that
will do the measuring (`~/tom_default/build/bin/llama-cli`, `b100-0967f4997`) with `-v -c 4096
-ngl 99 -sm layer`, and the gating function read back out of `print_info`:

| | base | REAP |
|---|---|---|
| `expert_gating_func` KV in file | `= 2` | **absent** |
| `print_info: expert_gating_func` | **sigmoid** | **sigmoid** |
| `print_info: arch` | deepseek2 | deepseek2 |
| `n_layer` / `n_vocab` | 47 / 154880 | 47 / 154880 |
| `n_expert_used` / `n_expert_shared` | 4 / 1 | 4 / 1 |
| `model params` | **29.94 B** | **23.00 B** |

Both resolve to sigmoid. **The arms are comparable on this build.**

**Correction to an earlier note in this receipt's first revision.** It recorded that none of the
builds on `.73` carried the compatibility shim. That was a grep-location error: this fork moved
per-architecture hparam loading into `src/models/*.cpp`, so the shim is not in `llama-model.cpp` at
all. It is `src/models/deepseek2.cpp:23-31`, and **all five build trees on `.73` carry it**
(`llama_stock_ref`, `buun_vbr`, `tom_default`, `tom_port`, `oscar-turboquant` — 1 hit each):

```c
ml.get_key(LLM_KV_EXPERT_GATING_FUNC, hparams.expert_gating_func, false);
if (hparams.expert_gating_func == LLAMA_EXPERT_GATING_FUNC_TYPE_NONE) {
    if ((hparams.n_layer() == 47 || hparams.n_layer() == 48) && n_vocab == 154880) {
        hparams.expert_gating_func = LLAMA_EXPERT_GATING_FUNC_TYPE_SIGMOID;   // GLM 4.7 Lite
    } else {
        hparams.expert_gating_func = LLAMA_EXPERT_GATING_FUNC_TYPE_SOFTMAX;
    }
}
```

The fragility assessment stands unchanged: the pruned arm is correct only because a hardcoded
heuristic recognises it, not because the file says what it means. **Re-run G-1a on any other binary
before measuring with it** — a build without this shim gives softmax on the pruned arm and sigmoid on
the base, silently.

### `-sm tensor` — refused for this architecture

`llm_arch_supports_sm_tensor()` (`src/llama-arch.cpp:1050`) is an **exclusion** list and
`LLM_ARCH_DEEPSEEK2` is on it, so `-sm tensor` throws at load:

```
LLAMA_SPLIT_MODE_TENSOR not implemented for architecture 'deepseek2'
```

It fails loudly rather than falling back, so there is no risk of silently comparing different split
modes. `-sm layer` is the only option. Partial DS split machinery exists in the tree
(`llama_meta_device_get_split_state` carries `blk.\d*.attn_(q_a|kv).weight` patterns) but the arch
gate still refuses.

### Two operational notes from the load

- **Set `-c` explicitly.** At default context the REAP arm allocated **30.3 GB across both cards**
  (15199 + 15159 MiB) for an 18.99 GB model — ~11 GB of KV — leaving both P100s at 15.2/16 GB. At
  `-c 4096` there is ample headroom and it loads faster. Record the value per §9.
- **Thinking is ON by default.** A two-token prompt emitted `[Start thinking]`. Confirms the mode
  axis is live and that IKP must explicitly disable it (see Modes in the spec) or the run cost is
  dominated by reasoning chains across 800 questions × 2 arms.

Also note the pruned file carries no `general.sampling.*` defaults. Irrelevant here because sampling
is set explicitly (spec: temp 0 both arms), but a client that reads defaults from the file would
sample the two arms differently.

## Hardware fit (`.73`, dual P100)

2 × Tesla P100-PCIE-16GB = 32 GB VRAM, idle at 150 W / 405 MHz (boosts to 1063; the fleet's
post-2026-07-17 state). System RAM is only **15 GB**, so CPU expert offload is not viable — but it is
not needed: base Q6_K at 24.69 GB and REAP at 18.99 GB both fit in 32 GB VRAM.

Pascal requires **layer-splitting** — `-fit off` — row-split crashes on P100 (per `CLAUDE.md`).
Record `-sm layer` / `-fit off` and the clock/power state with every result (§9).

Disk: `/mnt/models` 236 G, 61 G free after both downloads.

## Status

- G-1 packaging parity — **PASS**
- G-1a gating-function runtime check — **PASS** (both arms sigmoid on `b100-0967f4997`)
- G-4 prune ratio — **PASS** (25% of experts; 29.94 B → 23.00 B params, card and measurement agree)
- G-2 instrument discrimination (IKP on base) — not started
- G-3 positive-verification harness (scored-count grep) — not started
- G-5 `no_answer` three-bucket accounting — not started
- K (repetition count) — still pending the determinism answer

Both arms load and generate on `.73`'s 2×P100 at `-c 4096 -ngl 99 -sm layer`, clocks 1063 MHz /
150 W. Nothing blocks Phase 1 except K and the G-2/G-3/G-5 harness work.
