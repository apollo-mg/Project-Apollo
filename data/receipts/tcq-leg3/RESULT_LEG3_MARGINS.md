# Leg 3 — the margin bench: buun's turbo3_tcq holds more headroom, at both depths measured

**The third leg buun asked for on 2026-07-07.** Legs 1 (KLD) and 2 (hazard + prefill bench) were
published; this one had never run. `.194` 4×P100 @ 1063 MHz / 150 W, 2026-08-08.

Harness is buun's own: `probe_router.py` → per-token `lp(chosen) − lp(runner-up)`, per case the
**minimum** over tokens (distance to the nearest argmax flip), then `paired_margins.py` for a
paired t across the shared routing cases.

Model: `Qwopus3.6-27B-Coder-heretic-Q6_K.gguf` — the same model legs 1–2 used
(`tcq_sweep_tom/meta.txt`). Provenance in `../MODEL_PROVENANCE.json`.

## Headline

| tier | n | mean(TOM−BUUN) | **t** | TOM>BUUN | BUUN>TOM | worst-case margin TOM / BUUN |
|---|---|---|---|---|---|---|
| **2048** | 120 | −0.1581 | **−4.05** | 44 | 76 | 2.827 / **3.069** |
| **8192** | 120 | −0.3096 | **−7.36** | 26 | **94** | 2.914 / **3.198** |
| 32768 | — | not run | | | | |

Negative mean = buun's margins are larger = further from flipping.

**buun's turbo3_tcq wins at both depths, and the gap is larger at 8k than at 2k** — win rate
76/120 → **94/120**, effect size 0.158 → 0.310. It wins in the tail too: buun's *worst* case sits
further from a flip than Tom's at both tiers.

**Read the win rate and effect size as primary, not `t`.** The paired t treats case-to-case
variation as the only noise source, so it answers "is the mean difference across these 120
prompts nonzero" — not "would this hold on another model or another run." With K=1, one model
and one task family, `t = −7.36` is a paired-test statistic, not a strength-of-evidence claim.
The direction is unambiguous at 94/120; the magnitude is not transferable.

**Two depths is not a curve.** 2048 → 8192 is a single doubling. The mechanism is plausible —
more KV under compression means more opportunities to erode a margin — but a trend needs the
32768 tier, which was not run.

## Why this leg exists at all: accuracy is blind here

Every arm scored **5/5 exact** on the routing task in the pre-flight, and the generated text was
**byte-identical across f16, turbo3 and turbo3_tcq**. Scored on correctness these codecs are
indistinguishable. The entire signal lives in the logprob margins — which differed on 5/5 cases.

That is the campaign's own lesson one level down: *when the question is subtle, diff the bytes,
never a metric derived from them.* Here even the bytes agree and only the margins move.

## Third independent instrument, same direction

| leg | instrument | result |
|---|---|---|
| 1 | median KLD @ 2k/8k | buun ~1.9× better, 22 % fewer argmax flips |
| 2 | frontier-hazard mean_KL | buun 1.96× better; wins every hazard statistic |
| **3** | **distance-to-flip, task-grounded** | **buun, 76/120 (2k) and 94/120 (8k) cases** |

Legs 1–2 were **shallow** (`n_prefix=128`, the documented limitation). Leg 3 at tier 8192 is the
first deep-context measurement in this comparison, and the codec advantage survives depth —
larger at 8k than at 2k, on the two depths measured.

## Gates

- **G-L3a prompt cache OFF** (`--cache-ram 0`) on every arm, asserted from the boot log and
  fatal if violated. `--no-cache-prompt` alone is a *per-request* default in these builds; the
  server-side reusable cache is separate and defaults to 8192 MiB. **The first run was killed and
  discarded for exactly this** — a warm prefix changes batch shape → reduction order → logprobs,
  and logprobs *are* the measurement.
- **Determinism pre-flight, both builds**, before any margin was collected: same 5 cases × 3
  repeats, **5/5 byte-identical on each arm** (`preflight_TOM_turbo3/`,
  `preflight_BUUN_turbo3_tcq/`), plus an f16 control. `-np 1` throughout.
- **Codec engaged**: `TURBO meansub: K-mean BAKED table (16 live layers)` on all 4 devices for
  buun's arm. Tom's build prints no such line — verified as a build difference, not a failure.
- `TURBO_AUTO_ASYMMETRIC=0` on Tom's arm; no substitution notice in any boot log.

## Declared variable: buun's arm runs a NEWER build than legs 1–2

Legs 1–2 used the 2026-07-06 tree. Leg 3's buun arm runs **master `02f8581c6`**. This was
deliberate:

- The old tree carries `38859deff`'s out-of-bounds write in `ggml_cuda_argmax`, which by buun's
  own description fires on **every greedy / temp≤0 sample** and can corrupt the allocation
  following the argmax output.
- **Tom's build has no such code path** — his `argmax.cu` is 91 lines with a single
  `dst[row] = argmax` and no `output_logprob` extension.
- Keeping the old tree would therefore have placed a known memory-corruption bug on **buun's side
  only**, in a comparison he requested. That is not a footnote-able bias.

**The codec itself is unchanged**: all 197 shared `tcq`/codebook sources are byte-identical
between the two trees (1 file removed, a `turbo1_tcq` flash-attention vector instance, a
different codec). So leg 3 measures the same codec legs 1–2 characterised. Surrounding kernels,
sampler and server code did move 394 commits — that is the declared delta.

Both of buun's determinism fixes are present in this build and confirmed as ancestors:
`6d76b27c5` (FA scratch scoped to backend contexts) and `b90873faf` (turbo mean init).

## Limits

- **Tier 32768 not run**, and this is the gap that would turn two points into a curve. Cost, at
  the prefill rates measured in leg 2 (Tom turbo3 135.3 t/s, buun turbo3_tcq 281.0 t/s) against
  ~36.5k-token prompts: ~270 s/case × 120 on Tom's arm ≈ 9 h, ~130 s/case × 120 on buun's ≈ 4.3 h,
  **≈13 h for the pair**. Deferred on runtime, not on difficulty.
- **K=1, temp 0.** Byte-determinism was verified, so repeats are exact; this is an existence
  proof at these settings, not a distribution over seeds.
- **One model, one task family.** Routing cases (`rd_*_c2`), one 27B coder model. The margin
  advantage is measured on this task, not claimed universally.
- **Codec-on-build-A vs codec-on-build-B**, not an isolated codec ablation — kernels, compile
  flags and FA implementation all differ between the forks, as in legs 1–2.
- **⚠ buun's arm ran with the affine tap ACTIVE; this is not a pure codec comparison.** The boot
  log shows `TURBO meansub: K-mean BAKED table (16 live layers)`, and `K_live=16` matches the
  `qwen35 n_layer=64` entry in `ggml-turbo-meansub-data.inc` exactly. That table contains **two
  entries total** — `qwen35` (64L, from `pfhead_27b_long.bin`) and `qwen35moe` (40L) — and
  `ggml_turbo_meansub_set_model()` requires an exact (arch, n_layer, n_embd) triple match, so any
  other model gets no tap at all. Qwopus3.6-27B matches; most models do not. **What leg 3
  measures is therefore `turbo3_tcq + a mean-subtraction calibrated on this model family` versus
  Tom's `turbo3`.** Separating the two would need a tap-disabled arm, which was not run.
- The **first 8192/32768 attempt returned HTTP 400 on all 240 cases**: the server was started
  with `-c 4096`, copied from the pre-flight, which only ever used the ~2.3k-token `rd_2048`
  cases. Re-run at `-c 12288`. No partial data from that attempt survives in the results.
