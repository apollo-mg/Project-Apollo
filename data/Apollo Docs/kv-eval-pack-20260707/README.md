# KV-Codec Eval Pack — KLD panel + Hazard panel

Two complementary fidelity harnesses for KV-cache (or weight) codecs, extracted from our
llama.cpp fork's eval stack, plus the measurement lessons we paid for (see `INSIGHTS.md` —
read it before trusting any number these tools print, especially anything that is a MEAN).

**Ground rule up front (rule 0):** everything here measures *fidelity to the fp16 model*,
not goodness. A codec can beat f16 on a downstream task while scoring worse on hazard.
Task accuracy is the only goodness metric; these are cheap, dense, deterministic proxies.

Both panels run against **stock upstream llama.cpp** for standard KV types (`q8_0`, `q4_0`,
`f16`, ...). A few hooks are fork-only and marked as such below.

---

## 1. KLD panel (`kld-panel/`)

Teacher-forced KL divergence vs an f16-KV logit base, over a `{KV type} × {context depth}`
matrix. The workhorse. Wraps `llama-perplexity --kl-divergence`, which is **upstream** —
no fork needed for the basic panel.

### Files
- `kv_kld_sweep.sh` — the matrix driver. Resumable (OK cells skipped on re-run); failures
  (OOM/segfault/timeout) recorded as `-` so one bad cell never sinks the sweep. Emits
  `results.tsv` + rendered `results.md` per run.
- `kv_common.sh` — shared config/lib (sourced, keep next to the sweep script). All knobs
  are env-overridable: `BIN_DIR`, `MODEL`, `DATASET`, `BASE_DIR`, `KV_TIERS`, `TYPES`,
  `KTYPE` (pin K, sweep V only), `CELL_TIMEOUT`, `FA`, `NGL`.
- `parse_kld.py` — per-depth panel + leaderboards from a directory of per-cell logs
  (`LOGDIR=... PREFIX=... DEPTHS=...`). Prints, per candidate per depth:
  `meanKLD  median  p95  p99  p99.9  maxKLD  RMSdp%  flip%`.

### Step 1 — generate logit bases (once per model × depth)

Run the model with **f16 KV** and save the full (compressed) logit distribution per scored
token. `--save-all-logits` / `--kl-divergence-base` are the same upstream flag: without
`--kl-divergence` it WRITES the base; with it, it READS it.

```bash
llama-perplexity -m model.gguf -f wiki.test.raw \
  -ctk f16 -ctv f16 -fa on -ngl 99 \
  -c 16384 --chunks 18 \
  --save-all-logits base_f16kv_ctx16384_18ch.kld
```

Repeat per depth tier. Our standard ladder: 2048/32ch, 8192/24ch, 16384/18ch, 32768/9ch.
Note the base file also carries the token stream — the later eval never re-tokenizes `-f`,
so corpus-file mismatches between base-gen and eval are harmless.

### Step 2 — run the sweep

```bash
BIN_DIR=/path/to/build/bin \
MODEL=/path/model.gguf \
DATASET=/path/wiki.test.raw \
BASE_DIR=/path/to/bases \
TYPES="q8_0 q4_0" \
./kv_kld_sweep.sh /path/run_dir          # or --shallow for the first tier only
```

By default `TYPES` auto-detects the build's *custom* KV types (anything `--help` advertises
beyond the standard set) — on stock upstream, set `TYPES` explicitly. Also built in: an
**effective-BPW probe** that reads the bytes each type ACTUALLY allocates (calibrated
against f16) and flags silent K/V substitutions — trust it over name-based bpw tables.

### What each cell reports
From the llama-perplexity output: Mean KLD (±ci), Median KLD, 99.9% KLD, Max KLD, PPL(Q),
ln(PPL ratio), RMS Δp, **Same top p** (→ true flip rate = 100 − same-top-p), seconds.
Only the **deep half of each window is scored** (n_pos = n_ctx/2 − 1, e.g. 8191 @16k) —
bake that into any token-count math.

### Fork-only hooks (need our fork, not upstream)
- `TURBO_KLD_DUMP=<path>` — per-token KLD dump (`i32 n_pos, i32 n_chunk, f32[chunk][pos]`),
  turns one run into every statistic offline (median/trim/frac>τ/positional buckets/
  split-half reliability). See INSIGHTS §"cookbook".
- `TURBO_SCORE_LAST_K=64` — **honest last-K scoring**: score only the last 64 positions
  per window (the true decode frontier). This is the `l64` statistic. See INSIGHTS §l64
  for why it exists (position-targeted protection is invisible without it).

---

## 2. Hazard panel (`hazard-panel/`)

Dense per-token flip/decision-risk panel vs f16, teacher-forced (P1.2). Complementary to
KLD: across codecs it ranks identically to trajectory-survival; within a codec, per-prompt
Spearman(hazard, first-divergence) ≈ 0 — it's a dense central statistic, not a brittle
extreme statistic. Produces a clean monotone codec ladder with no floor saturation.

### Files
- `frontier-hazard.cpp` + `CMakeLists.txt` — standalone example tool. Uses only the public
  `llama.h` API, so it drops into **any** llama.cpp tree: copy the folder to
  `examples/frontier-hazard/`, add `add_subdirectory(frontier-hazard)` to
  `examples/CMakeLists.txt`, build target `llama-frontier-hazard`.
- `hazard_metrics.py` — offline variant: computes the same lens from artifacts you already
  have (the base logits file + per-cell `TURBO_KLD_DUMP` dumps), no extra GPU runs.
  Also the streaming margin extractor (~7 min for a 32GB base). Fork-dump dependent.

### How it works (frontier-hazard)
Loads the model once, builds two contexts — reference f16/f16 KV and the quant KV under
test — and feeds both the SAME real token prefix with logits requested at scored positions
(one `llama_decode`, no autoregression: per-step error never compounds into a one-shot
flip, keeping a graded signal where autoregressive harnesses saturate). Per scored
position t (f16 dist P, quant dist Q, full vocab):

```
a       = argmax P                        (f16 top-1)
F_t     = [argmax Q != a]                 (top-1 flip)
margin  = p[a] - p[2nd]                   (f16 decision margin, prob)
KL      = sum_v p_v (log p_v - log q_v)
R_t     = KL / (0.5·margin² + eps)        (decision-danger: KL per unit of margin)
L_t     = (gapP - gapQ) / (gapP + eps)    (logit-margin erosion; ≥1 ⇒ f16 margin erased)
```

Per prompt: `flip_rate, mean_R, cvar95_R (mean of worst 5%), mean_L, frac_Lge1, mean_KL`,
plus depth-band aggregates (0-128 / 128-512 / 512-2k / 2k-8k / 8k+) for a hazard-vs-depth
curve. `mean_L` is noisy; `frac_Lge1` is the usable margin-erosion statistic.

### Run

```bash
./build/bin/llama-frontier-hazard -m model.gguf -f prompts.txt \
  -ctk q4_0 -ctv q4_0 -ngl 99 --n-prefix 8192 --n-score 256 --max-prompts 128
```

**Always run the anchor first**: `-ctk f16 -ctv f16` must print all-zeros
(flip_rate = mean_R = ... = 0.0000 exactly). If it doesn't, something is broken —
fix that before reading any codec number.

Reference ladder from our 8-codec sweep (Qwen3.6, 128 wikitext prefixes, n_prefix=128):

| codec | flip_rate | mean_R | frac_Lge1 | mean_KL |
|---|---|---|---|---|
| f16 (anchor) | 0.0000 | 0.00 | 0.0000 | 0.00000 |
| q8_0 | 0.0115 | 6.3 | 0.0113 | 0.00041 |
| q4_0 | 0.0261 | 40.5 | 0.0251 | 0.00261 |

### Provenance
The panel is our build (2026-06), but the grounding is external: true flip-rate comes from
llama.cpp's own `llama-perplexity` "Same top p" output; the trajectory/flip framing traces
to the TurboQuant GitHub discussion #20969 (contributor sztlink's `trajectory` metric =
% of greedy steps whose argmax matches f16). `R_t = KL/(½·margin²)` is our second-order
flip-probability proxy on top. Validated against TRUE argmax flips at ρ +0.84…+0.96.

---

## 3. Which one do I use?

- **Ranking codecs / regression-gating a build:** KLD panel, judged on **median** (and
  read INSIGHTS before using the mean for anything).
- **"Will this codec flip decisions?"**: hazard panel (`flip_rate`, `mean_R`), or the free
  true-flip number already in every KLD cell log (`Same top p`).
- **Position-targeted schemes (sink/recency protection, VBR):** you MUST score at the
  decode frontier (`TURBO_SCORE_LAST_K=64` / l64) — full-window scoring cannot see it.
- **Fine transitions near the noise floor (fp16→q8-class):** catastrophe fractions from
  paired dumps, not any magnitude statistic. See INSIGHTS §floors.
