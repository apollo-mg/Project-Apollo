# Margin bench — task-grounded eval for KV-cache codecs

This is the harness we use instead of (well, alongside) KLD to decide whether a KV
codec change is actually good. We built it after KLD burned us several times. If
you're staring at KLD tables wondering why your "wins" don't feel like wins — this
is the way out we found.

## The four traps (each one cost us real time)

**Trap 1 — KLD is fidelity-to-fp16, not goodness.** KLD measures divergence from
the fp16 run. A codec change that *routes around* fp16's own quirks raises KLD
while improving real outcomes. We have a weight-quant config that beats BF16 on
AIME (26/30 vs 18/30) with *worse* KLD. If you gate on KLD alone you will reject
genuinely good changes. Final arbiter must be task-grounded.

**Trap 2 — mean KLD is tail-dominated.** The mean is dragged by a few catastrophic
positions; bulk improvements vanish into it. Our V-mean subtraction tap moved mean
KLD by ~1% (t≈0.3, pure noise) — and tripled worst-case task margins (t=+8.5,
117-vs-3 paired wins). A mean-KLD gate would have rejected half of one of our best
changes. If you must use KLD: paired per-position differencing, and look at
median/p99/last-window separately, never just the mean.

**Trap 3 — exact-match saturates.** A capable model aces a task across every codec
and depth (we got 120/120 on every config — zero discrimination). The signal isn't
*whether* the model answers correctly, it's **how close it came to flipping**.
That's what logprob margins measure.

**Trap 4 — single draws are coin flips.** Pass/fail deltas on one seed regress to
the mean on reseed (we "recovered" 6 hard problems with a better codec; 4 of them
re-passed under the *old* codec with a new seed). Use paired per-case statistics
on a fixed case set — or multi-seed. Never trust one draw.

## What this harness does

Synthetic long-context **routing cases**: an evidence package (action / target /
source-rank) is buried at depth behind tunable noise and confusable distractors,
so the model must read it back *through your quantized KV cache*. Greedy decode,
fixed cases. For every answer token we record logprob(chosen) − logprob(runner-up);
a case's score is the **minimum margin** = calibrated distance-to-flip. Comparing
two configs = paired per-case differences on identical cases → a t-statistic.

It separates 2-bit / 3-bit / 8-bit KV codecs at 5–12σ in a few minutes per config
on a 4B model, at depths where exact-match shows nothing.

## Quickstart

1. Serve your config (one slot, no batching — keep runs deterministic):

```
./llama-bench/bin/llama-server -m model.gguf -ngl 999 -c 12288 \
  -ctk <your_kv_type> -ctv <your_kv_type> -fa on -np 1 \
  --host 127.0.0.1 --port 8099 --jinja
```

2. Probe it (≈120 cases, sequential, greedy):

```
python3 router_probe/probe_router.py \
  --data router_probe/cases/rd_8192_c2.jsonl \
  --out lp_myconfig.jsonl --label myconfig
```

3. Repeat with your baseline config (`lp_baseline.jsonl`), then:

```
python3 paired_margins.py lp_myconfig.jsonl lp_baseline.jsonl
```

You get: mean paired margin delta, t-stat, per-case win counts (A>B / B>A), each
cell's worst-case margin, and the six closest-to-flip cases per config.

## Reading the output

- **t > ~3** with a lopsided win count = real effect. |t| < 2 = stop, it's noise.
- **minA / minB** (worst-case margin) is the number that predicts production
  failures — a config whose worst case sits at 0.3 nats is one unlucky sample
  away from a flip; 2.5 nats is comfortable. We weight this over the mean.
- Margins are model-relative: compare configs on the **same model, same build,
  same cases**. Don't compare absolute margins across models.

## Notes

- Cases: `rd_2048_c2` / `rd_8192_c2` / `rd_32768_c2` (depth sweep; c2 =
  confusability tier). `gen_router_cases.py` regenerates or makes harder tiers
  if your model saturates these (fix the seed and reuse the same file for every
  config you ever compare).
- The probe sends `chat_template_kwargs: {"enable_thinking": false}` (Qwen-style);
  harmless elsewhere, adjust if your template differs.
- 32k cases need `-c` ≥ 36000ish on the server.
- Case design credit: depth/confusability extension of sztlink's kv-score router
  probes.
