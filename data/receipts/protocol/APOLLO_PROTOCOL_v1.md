# Apollo Protocol v1 — working draft

**How to run a local model on the VRAM you actually have, and how we test it.**

Status: **working draft.** Numbers marked *measured* were taken on this fleet with the
commands shown. Numbers marked *worked example* are arithmetic from those measurements.
Anything not marked is not yet established.

## What this is for, and what it is not

**For:** someone with a fixed amount of VRAM who wants to know what they can actually run,
what it will feel like, and how much quality they are giving up to get there.

**Not for:** unified/integrated-memory systems, or anyone with datacentre parts. Those are
well-covered by people with the hardware. This protocol targets **discrete consumer and
ex-datacentre GPUs in the 16-64 GB range**, which is where the fleet lives and where the
advice is thinnest.

**Not a leaderboard.** No score here is comparable to a published benchmark number unless it
says so explicitly and states the harness.

---

## Step 0 — your card is smaller than the box says

The single most common planning error. **Nominal capacity is not usable capacity**, and the
gap is largest for exactly the people this protocol is for: those running a desktop on the
same card as the model.

*Measured, RX 9070 XT, CachyOS desktop session live, browser open:*

| | MiB | |
|---|---:|---|
| marketed | "16 GB" | |
| addressable (`mem_info_vram_total`) | **16,304** | −1.5 % vs marketing |
| **consumed by the desktop** | **2,555** | compositor, browser, video decode |
| **free for a model** | **13,749** | **13.4 GiB — a 16 % haircut** |

```bash
# AMD
cat /sys/class/drm/card*/device/mem_info_vram_total   # bytes, addressable
cat /sys/class/drm/card*/device/mem_info_vram_used    # bytes, in use right now
# NVIDIA
nvidia-smi --query-gpu=memory.total,memory.used --format=csv
```

**Take the reading with your normal desktop running**, not at a bare TTY. And treat it as a
*floor*, not a budget: desktop usage **grows** — a video call, a game launcher, a browser tab
with WebGL. A model sized to the last free megabyte will OOM when you open Slack.

**Rule of thumb: subtract another 1 GiB on top of what you measure**, or run the model on a
card that is not driving a display.

**Headless is worth ~2.5 GiB.** On a 16 GB card that is the difference between a 9B at long
context and a 9B at short context. It is the cheapest upgrade available and it costs nothing.

## Step 1 — measure your model's KV cost. Do not compute it.

KV cost per token is set by **model architecture**, and the obvious formula is **wrong on
modern hybrid models**.

*Measured, Qwen3.8-27B (`arch qwen35`):*

| | values/token | bytes/token @ f16 |
|---|---:|---:|
| naive formula `n_layer x n_head_kv x (d_k + d_v)` | 131,072 | 256 KiB |
| **actually measured** | **32,768** | **64 KiB** |

**4× overestimate.** Cause: only ~16 of its 64 layers carry a KV cache at all — the rest use
Lightning/linear attention with O(1) state. Nothing in the published parameters says so.

Measure it with two loads and take the **slope** (a fixed per-context overhead exists — ~128
KiB on turbo KV types — so a single reading is a rate only by accident):

```bash
for CTX in 4096 16384; do
  <your llama.cpp binary> -m MODEL -ngl 99 -c $CTX -ctk f16 -ctv f16 ... 2>&1 |
    grep "KV buffer size"     # sum across ALL devices
done
bytes_per_token = (bytes@16384 - bytes@4096) / 12288
```

## Step 2 — pick a target, then derive the budget

Fix **what you want**, not how much memory to spend. The target is the thing that stays
constant across machines and models; a fixed MiB number does not.

```
target        : e.g. "260k tokens at >= 6 bits/value"
budget_bytes  = target_ctx x bytes_per_token(f16) x (target_bpv / 16)
```

*Worked example, Qwen3.8-27B, 260k tokens:*

| `VBR_BUDGET_MIB` | full f16 until | bits/value @260k |
|---:|---:|---:|
| 4096 | 65,536 tok | 4.03 |
| **6144** | **98,304 tok** | **6.05** |
| 8192 | 131,072 tok | 8.07 |

Then check it against **the smallest machine that must run it**, using your Step 0 number.

## Step 3 — pin the KV budget; do not let it float

We run **VBR (variable-bit-rate KV) with `VBR_BUDGET_MIB` pinned**, and we recommend it.

**Why VBR:** one flag adapts to context depth instead of forcing you to hand-size a KV type
per (machine × model × context). It starts at f16 and degrades only under real pressure.

**Why pinned, and this is not optional:** left alone, VBR derives its budget from *live free
memory*, so the same command produces different arithmetic on a different machine — or on the
same machine with a browser open. **Pinning makes it reproducible.** The build documents this
path as *"forced-budget instrumentation must never grow"*.

Two operational notes: dynamic VBR needs `--kv-unified` and flash attention on (the CLI
handles the first for you), and **context shift / self-extend are disabled under it** —
generation stops cleanly when the context fills rather than silently dropping your earliest
tokens.

## Step 4 — prove the stack works before you trust any number

Four tiers. **Tiers 1-2 are gates; 3-4 are reports.**

| tier | question | items | gate |
|---|---|---:|---|
| **1 plumbing** | server up, template applied, format obeyed, judge working | 5 trivial | **5 of 5** |
| **2 model sanity** | weights/quant/sampling not degraded | 10 moderate | **>= 6 of 10** |
| **3 headroom** | how much capability is left | 10-20 hard | report only |
| **4 deployment shape** | what it is like to actually use | — | report only |

**Use easy questions for the gates.** With a threshold gate, easy items (working ≈95 %,
broken ≈10 %) separate a working stack from a broken one at **97.7 % vs 0.0 % on five
questions**. Hard items at 15 %/5 % give **67.8 % vs 6.1 % even at thirty** — a gate that
fails a healthy stack a third of the time. When the working stack's own ceiling is low, no
sample size rescues the gate.

**Tier 4 metrics:** TTFT at realistic depth (not at zero context), **inter-token latency
p50/p99** (the "1 % lows" — a mean hides an 800 ms stall every twelfth token), sustained
throughput over 10+ minutes, **measured** tokens/joule, usable context at the pinned budget,
and the quality-vs-depth curve.

## Reporting rules

- **No metric without its distribution.** A mean ships with its tail or not at all.
- **Every claim carries its config**: model, quant, KV type, pinned budget, measured
  bytes/token, sampling params, system prompt, and **GPU clock/power state**.
- **Failed arms are reported as failures**, not filled in with a non-comparable substitute.
- **Vendor numbers are hypotheses.** Establish what was actually claimed — which subset, which
  judge, what token budget, how many samples — before matching or disputing it.

---

## Scenarios *(skeleton — needs the dry run before these are quotable)*

The decision procedure, not a lookup table, because Step 1 says the numbers are per-model.

| you have | realistic budget after Step 0 | what to reach for |
|---|---|---|
| 16 GB, **driving a display** | ~13.4 GiB *(measured)* | mid-size model; a 22 GiB model does **not** fit |
| 16 GB, **headless** | ~15.9 GiB | same class, meaningfully more context |
| 32 GB (2 × 16) | ~31 GiB | 27B-class + a real KV budget |
| 64 GB (4 × 16) | ~63 GiB | 27B-class at long context, or larger weights |

**Deliberately unfilled.** Populating it needs the dry run: for each class, measure
bytes/token, derive a budget, run tiers 1-2, then report tier 4. Filling it from arithmetic
alone would be exactly the spec-sheet advice this protocol exists to replace.
