# P100 lab harvest — small result files rescued from `.194` before base-file cleanup

Harvested 2026-07-29 from `10.0.0.194:/home/mark/`. **289 files, 18 MB.**

## Why

`.194` is at **26 GiB free on a 98 %-full 915 GB volume**, which blocks staging any further
model quant (a Laguna Q4 rung needs ~55–60 GiB). Six working directories hold **~212 GB**, but
almost all of that is one file type: `.kld` KLD reference bases and raw logit dumps.

Those are **derived intermediates** — regenerable from the model + the original command, and
inert once their campaign is scored. The actual results sitting next to them are logs, reports
and JSON measured in kilobytes. Hence: rescue the small files first, so nothing irreplaceable
is ever in a delete set.

| source dir | total | bulk (regenerable) | harvested here |
|---|---|---|---|
| `puzzle_lab` | 92 G | `w1/q8_base_logits.bin` 69 G, `w1/*.kld` 16 G, `*.kld` 8 G | 85 files |
| `quant_ladder` | 16 G | `qwen27b_bf16_truth_*.kld` 16 G | 196 files |
| `moe_panel` | 16 G | `moe36b_f32kv_*.kld` 16 G | 7 files |
| `slots` | 14 G | KV checkpoint canaries (`*.bin`) | 1 file |
| `qwen-base-logits-kld` | 46 G | 3 × 16 G `.kld` | **0 — contains only `.kld`** |
| `turbo-logits-kld` | 38 G | 1 × 38 G `.kld` | **0 — contains only `.kld`** |

## What's in here

- `puzzle_lab/` — W1 dense control runs (llama-bench Q8_0 sweeps with full device banners and
  t/s tables), imatrix panel logs, KLD run logs, download verification
- `quant_ladder/` — the largest set: A/B build logs, `ab_results.txt`, per-config server logs
  (layer/row × carveout/fastpath), NLL dumps at depth 8192
- `moe_panel/` — MoE cell comparison logs (M1 f16-fa-on, M2 q8-fa-on vs patched base)
- `slots/` — KV checkpoint canary log

Spot-checked after extraction: `puzzle_lab/w1/w1_report.txt` opens with intact llama-bench
tables (4× P100, 65,077 MiB total VRAM, Q8_0 pp512 125.08 ± 0.02 t/s), so the archive is
readable, not just present.

## Not yet deleted

Nothing on `.194` has been removed. This harvest exists so the deletion can be reviewed
against a complete list of what survives it. Two cautions carried forward:

1. **Campaign-completion is unverified.** I have not confirmed every campaign these bases
   belong to is finished and receipted. `quant_ladder` was last touched **2026-07-20**, the
   most recent of the group.
2. **Regeneration costs GPU-hours.** A 16 G base is cheap to delete and not free to rebuild.

The cleanest starting point is `qwen-base-logits-kld` + `turbo-logits-kld` (**84 GB, zero
result files, nothing to lose**) — that alone exceeds what a Laguna Q4 rung needs.
