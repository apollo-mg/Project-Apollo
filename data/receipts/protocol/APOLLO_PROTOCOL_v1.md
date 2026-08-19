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

## Step 5 — the real decision is the weights/KV split, not "which model"

**Correction to an earlier draft of this document**, which listed scenarios by model and said
a 27B "does not fit" in 16 GB. That conflated a model with one quantisation of it. A 27B at
Q6_K is ~21 GiB; the same 27B ternary is ~5. They are different products sharing a name.

At a fixed VRAM budget **weights and KV compete**, and that competition is the actual choice.

*Worked example: 27B-class, 13.4 GiB free (16 GB card driving a display), 0.8 GiB for compute,
KV priced at the measured 64 KiB/token:*

| weights | size | left for KV | context @6 bpv | context @f16 |
|---|---:|---:|---:|---:|
| ternary ~1.6 bpw | 5.0 GiB | 7.6 GiB | **331k** | 124k |
| IQ2_XXS ~2.1 | 6.6 GiB | 6.0 GiB | **262k** | 98k |
| Q3_K_M ~3.9 | 12.3 GiB | 0.3 GiB | **15k** | 6k |
| Q4_K_M ~4.8 | 15.1 GiB | — | **does not fit** | |
| Q6_K ~6.6 | 20.7 GiB | — | does not fit | |

**There is a cliff, not a gradient.** Between IQ2_XXS and Q3_K_M the usable context falls
**262k → 15k**. Q3_K_M "fits" in the sense that the weights load, and is close to useless for
long work because nothing is left for the cache.

**So low-bit weights are not the consolation prize on a 16 GB card — they are the thing that
buys usable context.** The interesting question is not *"how much quality do I lose going to
IQ2"* but *"how much quality do I lose going to IQ2, **and how much do I gain back by having
20× the context and a KV budget that never degrades**"*. That trade has, as far as we know, not
been measured by anyone, and this fleet can measure both halves.

*Caveat carried from Step 1:* the KV column assumes the **measured** 64 KiB/token of this
hybrid architecture. A conventional 27B with full attention on every layer costs ~4× that, and
every context number above would fall by the same factor. **Measure your model.**

### Units, since this trips people constantly

Model files are listed in **GiB** (1024³); GPUs are marketed in **GB** (10⁹). A "16 GB" card
holding a "15 GB" model sounds comfortable and may not be. Always compare like with like — and
note that on the card measured here, "16 GB" really is ~16 GiB, so the direction of the error
is not even consistent between vendors.

---

## Scenarios *(skeleton — needs the dry run, and needs a model list)*

| you have | usable after Step 0 | the decision |
|---|---|---|
| 16 GB, **driving a display** | ~13.4 GiB *(measured)* | low-bit weights buy context; the cliff sits around 3 bpw for a 27B |
| 16 GB, **headless** | ~15.9 GiB | +2.5 GiB — one quant tier up, or ~40k more context |
| 32 GB (2 × 16) | ~31 GiB | 27B at 4-6 bpw with a real KV budget |
| 64 GB (4 × 16) | ~63 GiB | 27B at 8 bpw long-context, or larger weights |

**Deliberately unfilled with specific models.** Populating it needs (a) the dry run and
(b) a current list of what is actually good at each bit level — which changes monthly and is
not something this document should guess at. Candidates raised so far, **unverified here**:
Bonsai's ternary Qwen 3.6 27B, Gemma 4 12B QAT, IQ2_XXS 27B paired with turboquant KV and a
compaction layer.

---

## Step 6 — engine churn: version the suite, not the engine

The tension, stated by Mark:

> *"I hate the idea of a benchmark suite using constantly different builds between tests, but
> maybe we have to think of the engine as more of a driver that you're supposed to keep up to
> date, even if it introduces new bugs that confound the shit out of all the tests."*

Both halves are right, and the resolution is not to pick one. **Pinning forever goes stale and
measures a fork nobody runs. Chasing head means every result sits on a different substrate.**
What works is the approach MLPerf uses for rounds and Gamers Nexus uses for driver versions:
**results are comparable within a declared version, and crossing versions requires a bridge.**

### The rule

1. **Pin the engine commit per campaign** and record it in every receipt. *(Already done — every
   receipt in this repo names its tree and SHA.)*
2. **Results are comparable within a pinned commit.** Across commits they are not, by default.
3. **On every bump, run the bridge arm on both the old and new commit.**
4. If the bridge agrees within tolerance, prior results **carry forward**. If it does not, they
   **do not** — and the bridge tells you by how much, which is more useful than either
   pretending the change is safe or discarding the history.

### The bridge arm costs nothing, because we already run it

Every fidelity panel here already contains two arms that serve as the bridge:

| arm | expectation | what a deviation means |
|---|---|---|
| **f16/f16** | an **exact null** — flip 0.0000, KL 0.00000 | the engine broke something fundamental; **stop** |
| **`q8_0`/`q8_0`** | the same `mean_R` within run-to-run noise | numerics moved; quantify before carrying anything forward |

*Reference values, buun `02f8581`, sm_60, 128 prompts, `--n-prefix 128`:*

| | |
|---|---|
| f16/f16 | `flip 0.0000  mean_KL 0.00000  mean_R 0.0000` |
| `q8_0`/`q8_0` | `flip 0.0014  mean_KL 0.00001  mean_R 0.1654  cvar95 3.3529` |

The bridge is **per (engine commit × backend)** — a HIP build and a CUDA build of the same
commit are different substrates and each needs its own reference row. The ≤1 pp cross-backend
acceptance gap measured in `S2` is the same phenomenon seen from the throughput side.

### Why this is worth the discipline

It converts engine churn from a confound into a **measurement**. Instead of *"the build
changed, who knows"*, you get *"the build changed and `q8_0` moved 4 %, so the depth panel
needs re-running but the throughput work carries"*. That is a decision you can defend, and it
takes minutes rather than re-running a campaign on faith.

It also catches the failure mode that has bitten this project repeatedly: **a tree that is not
what its name says.** `llama_stock` on `.194` was not stock; three trees on the fleet have been
mislabelled. A bridge arm run on checkout would have caught every one of them immediately.

### Corollary: match commits across nodes before comparing nodes

A cross-node comparison on different commits measures the commit difference as well as the
hardware. The buun fork was built for RDNA4 at **`02f8581`** specifically to match `.194`,
rather than at the 2.5-week-older `7939b6c4` that was already checked out — otherwise "VBR on
RDNA4 vs Pascal" would have silently included two weeks of upstream drift.
