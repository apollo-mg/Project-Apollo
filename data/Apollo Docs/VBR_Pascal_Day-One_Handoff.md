# VBR on Pascal — Day-One Validation (handoff pack for buun)

**Date:** 2026-07-10 (launch day). **Rig:** 4× Tesla P100-PCIE-16GB (sm_60), driver 580.159, CUDA 12.4,
node `.194`. **Model under test:** Qwopus3.6-27B-Coder-heretic Q6_K (+ base Qwen3.6-27B Q6_K for the
ablation). **Corpus:** wikitext-2 test.
**Builds:** VBR runtime tests = fresh master clone `72fdec770` (launch push). KLD ladder + ablation =
`~/buun_tree` (sync-upstream-20260706 lineage — same binary for every quality cell; cross-build base
sharing validated by an exact-zero f16 anchor, receipts below).

---

## 1. Three wins (mechanism fully functional on 9-year-old silicon)

**W1 — Dynamic VBR engages on sm_60; VMM works; no fallback.**
```
VBR dynamic runtime controller: KV budget 1024 MiB (explicit), entry tier f16, floor 1.25 bits/value
VBR_VMM gate: dynamic=1 ... -> wanted=1
VBR VMM pool #0: 4100.00 MiB VA reserved (device 0, 2048 KiB pages), 4.00 MiB mapped up front
VBR VMM pool #1: 4096.00 MiB VA reserved (device 1, ...)
```
The `cudaMalloc` fallback never fired. Coherent generation (read, not just scored).
Pascal is now the oldest hardware VBR is confirmed live on.
Receipts: `.194:/home/mark/vbr_logs/a1_serve.log`, `a3_fast_fix.log`.

**W2 — The degrade cascade fires correctly under pressure, budget honored, no OOM.**
`--vbr-vram 1G`, `-c 32768`, ~17k-token prefill. f16 KV costs 72 KiB/token on this model (measured
via the allocation probe: 144 MiB per 2048 tokens), so a 1024 MiB budget breaches at ~14.5k tokens —
and the controller triggered exactly there. **26 degrade steps**, one (layer, side) at a time,
walking the price order (first: `cache_k_l63 L63 -> turbo8`, "14336 cells transcoding on side
stream"), prefill completed gracefully inside the cap.
Receipt: `.194:/home/mark/vbr_logs/a3_fast_fix.log` (grep `VBR degrade #`).
Also verified: dynamic mode disables `--slot-save-path` at init with a clean warning and returns
HTTP 501 on the endpoint — the documented contract holds.

**W3 — Codec quality ORDERING is perfectly preserved on Pascal.**
Same-build ladder (buun_tree, one binary, one f16 anchor, wikitext-2):
f16 anchor exact zero at 2k/8k/16k (median −1e-5, same-top 100.000%); allocation probe all-OK
(f16 16.000 / q8_0 8.500 / turbo4 4.124 / turbo3_tcq 3.249 — no silent substitution).
Median KLD ordering q8_0 < turbo4 < turbo3_tcq at every depth, stable 2k→16k. **The baked price
order VBR walks remains valid on Pascal.**
Receipts: `.194:/home/mark/buun_ladder_run/{results.tsv,results.md,bpw.tsv}`.

## 2. One caveat (why we're asking for 5 minutes of your 3090)

**Absolute median-KLD scale on our Pascal rig runs ~4–10× your README table**, largest at the fine
end, orderings intact:

| codec | your 3090, base Qwen @16k/18ch | our P100, base Qwen @2k/32ch | our P100, Qwopus @2k | gap |
|---|---|---|---|---|
| q8_0 | 0.00020 | 0.002126 | 0.001854 | **10.6×** |
| turbo4 | 0.00090 | 0.004324 | 0.003873 | 4.8× |
| turbo3_tcq | 0.00163 | 0.006141 | 0.005309 | 3.8× |

What we've excluded:
- **The abliterated finetune is innocent** — the base-model ablation reads the same (marginally
  worse, ~15%, consistent across all three codecs). Receipt: `.194:/home/mark/qwen_base_ablation/results.tsv`.
- **Depth largely excluded** — Qwopus medians are flat 2k→16k on our rig, so 2k-vs-16k doesn't
  explain it.
- **Not your codecs specifically** — plain upstream q8_0 shows the LARGEST elevation. Whatever this
  is, it isn't TCQ/turbo code.

What we have NOT isolated: which platform component (Pascal numerics/FA path vs 4-way layer split
vs something in our config). The gap structure — 10.6×→4.8×→3.8× compressing as codecs coarsen —
fits an **additive platform noise floor ≈ 0.0019** that dominates fine codecs (striking fit at q8_0:
0.0002 + 0.0019 = 0.0021 vs measured 0.00213). Hypothesis, not conclusion.

Practical deployment note either way: on Pascal the *relative* quality cost of coarser tiers is much
smaller than the 3090 table suggests (q8_0→turbo4 is ~2× here vs ~4.5× there) — budget-hardware
users get the VRAM savings comparatively cheaper.

## 3. The ask (one command pair, ~5 min on the 3090)

Same config as our cells — base Qwen3.6-27B Q6_K, wikitext-2 test, 2k/32ch — only silicon differs:

```bash
# 1) f16 logit base @2k/32ch
llama-perplexity -m Qwen3.6-27B-Q6_K.gguf -f wiki.test.raw \
  -ctk f16 -ctv f16 -fa on -ngl 99 -c 2048 --chunks 32 \
  --save-all-logits base_q6_f16kv_ctx2048_32ch.kld
# 2) the q8_0 cell against it
llama-perplexity -m Qwen3.6-27B-Q6_K.gguf -f wiki.test.raw \
  -ctk q8_0 -ctv q8_0 -fa on -ngl 99 -c 2048 --chunks 32 \
  --kl-divergence-base base_q6_f16kv_ctx2048_32ch.kld --kl-divergence
```

- Median KLD **≈ 0.0002** → config excluded; the elevation is Pascal-side. Your README numbers are
  Ampere+ expectations and Pascal users should read the ordering, not the absolutes.
- Median KLD **≈ 0.002** → it's the config (chunks/depth after all), our numbers align with yours,
  and the caveat evaporates.

Either outcome is clean; we just don't want to say "Pascal floor" publicly without the cross-lab cell.

## 4. The offer

Tier-aware save/restore for VBR (your "up your alley" nudge): design spec drafted —
`VBR_Tier-Aware_Save-Restore_Spec.md`. Core moves: tier map serialized as data (string codec tags),
restore never upgrades, restore-fit reuses your degrade machinery, sidecar carries hybrid
checkpoints (our llama-cpp-turboquant patch ported). §9 has five design-veto questions — worth 10
minutes before any code. Your A3 log already half-answers Q1: the side-stream transcode path exists,
so restore-fit can likely call it verbatim. Acceptance target: byte-identical next-64-token logits
on same-budget restore, degrade-at-restore priced (median + l64), graceful fallback proven.

## Receipt index (.194)
```
/home/mark/vbr_logs/a1_serve.log           # VMM pools, controller armed, coherence run
/home/mark/vbr_logs/a3_fast_fix.log        # 1024 MiB explicit budget, 26-step cascade, no OOM
/home/mark/buun_ladder_run/                # same-build ladder: anchor, bridge, turbo4, tcq3
/home/mark/qwen_base_ablation/results.tsv  # base-model ablation (abliteration exonerated)
/home/mark/turbo-logits-kld/               # Qwopus f16 bases (8k/16k; 2k deleted for space, regen ~5min)
/home/mark/qwen-base-logits-kld/           # base-Qwen f16 base (2k/32ch)
```
