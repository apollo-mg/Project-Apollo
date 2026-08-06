# Lab Spec — Nemotron Puzzle-75B: MoE Economics at Home (2026-07-19)

**Thesis for the writeup:** Puzzle-75B is a model most people can't run today but will want to,
and the two numbers they need for upgrade planning — decode speed and VRAM-at-context — are
both badly mispredicted by the rules of thumb currently in circulation.

Node: .194 (4× P100, 150W/1063MHz, no P2P). Build 9937 (73a55486c). **Blocked until the W3
Qwen IFEval leg lands (~04:30 EDT 2026-07-20) — do not disturb port 8091 before then.**

---

## 1. Architecture (measured 2026-07-19, GGUF header only — not assumed)

Read via a dependency-free header parser (`scratchpad/gguf_kvmeta.py`); metadata only, no
tensor data.

| | Puzzle-75B-A9B UD-IQ4-XL | Qwen3.6-27B Q8_0 |
|---|---|---|
| arch string | **`nemotron_h_moe`** | `qwen35` |
| blocks | 90 | 64 |
| layers with attention | **9 of 90** (`head_count_kv=2`) | 64 of 64 (`head_count_kv=4`) |
| head k/v length | 128 / 128 | **256 / 256** |
| experts | **512**, per-layer `expert_used_count` 0→22 | dense |
| trained context | **1,048,576** | 262,144 |
| weights on disk | 41.62 GiB | 26.63 GiB |
| **KV bytes/token (f16)** | **9,216** | **262,144** |

**Puzzle is not simply an MoE — it is a Nemotron-H *hybrid*: 81 of its 90 layers are
attention-free (SSM/Mamba-class), and only 9 carry a KV cache at all.** The expert count is
also heterogeneous per layer (NAS-derived), ranging 4→22 active experts, with many layers using
none. This matters for every claim below, and it invalidates reasoning that treats the model as
"a 75B MoE with 9B active."

Arithmetic check: Puzzle 9 × 2 × (128+128) × 2 B = 9,216 B/tok. Qwen 64 × 4 × (256+256) × 2 B =
262,144 B/tok. **Ratio 28.4×.**

## 2. The KV finding (already established — this is a result, not a plan)

Mark's premise was that MoE KV caches are smaller and "more than compensate" for the larger
weights. **Confirmed, and understated — but the mechanism is hybrid-SSM depth, not MoE-ness.**
Expert count has no bearing on KV size; 81 attention-free layers and a 128 head-dim do.

Total VRAM = weights + KV × context × slots:

| Aggregate context (1 slot) | Puzzle total | Qwen total | Winner |
|---|---|---|---|
| 16,384 | 41.76 GiB | 30.63 GiB | Qwen by 11.1 |
| ~63,600 | 42.17 GiB | 42.19 GiB | **crossover** |
| 131,072 | 42.74 GiB | 58.63 GiB | Puzzle by 15.9 |
| 262,144 (Qwen max) | 43.87 GiB | 90.63 GiB | Puzzle by 46.8 |
| 1,048,576 (Puzzle max) | **50.6 GiB** | not trainable | Puzzle |

**Crossover ≈ 63.6k tokens of aggregate context.** Below it the dense 27B is cheaper; above it
the 75B hybrid is cheaper *in absolute VRAM*, while being 2.8× the parameters.

Concurrency, on a 64 GiB rig at 16k/slot: Puzzle ≈ 159 slots, Qwen ≈ 9 slots. **~17×.**

## 2c. RETRACTION — §2 and §2b are both WRONG (2026-07-19, second correction)

**Qwen3.6-27B is also a hybrid. I computed its KV as if all 64 layers cached; only 16 do.**
Caught by an r/LocalLLM post (Last_Bad_2687, Strix Halo) noting qwen3.6 "types layers by
position". Verified in its own GGUF header:

```
qwen35.full_attention_interval = 4      qwen35.ssm.state_size  = 128
qwen35.ssm.conv_kernel         = 4      qwen35.ssm.inner_size  = 6144
```

`full_attention_interval=4` ⇒ 16 of 64 layers carry KV; the other 48 are gated-deltanet
recurrent layers. Corrected: **Qwen = 65,536 B/token, not 262,144 — a 4× overstatement.**

| | Puzzle-75B | Qwen3.6-27B |
|---|---|---|
| attention layers | 9 / 90 | **16 / 64** (was assumed 64/64) |
| kv heads × (k+v) len | 2 × 256 | 4 × 512 |
| **KV bytes/token** | 9,216 | **65,536** (was 262,144) |
| ratio | — | **7.1×** (was 28.4×) |

Corrected economics at f16: Puzzle@1M = 50.6 GiB, **Qwen@262k = 42.6 GiB (was 90.6)**.
Crossover moves 63.6k → **285.8k tokens**. On 64 GiB, Qwen reaches **612k** of capacity at
f16 — comfortably past its rated 262k. Qwen's fixed recurrent state is only ~74 MiB/sequence.

**Everything headline-shaped in §2/§2b is dead:**
- ✗ "The bigger model is the one that fits" — false at f16; Qwen@262k (42.6) beats Puzzle@1M (50.6).
- ✗ "Qwen cannot reach its rated context at full KV precision" — false; it has 2.3× headroom.
- ✗ "28.4× KV advantage" — it is 7.1×.

**What actually survives:** Puzzle's per-token KV is genuinely ~7× smaller, so it holds ~2.6M
tokens of capacity on 64 GiB against Qwen's 612k (~4.3×, ratio-invariant under quantisation),
and it is rated to 1M context where Qwen stops at 262k. That is a real capacity story, just not
a VRAM-frugality story.

**Root cause of the error, for the methodology file:** I read Puzzle's `head_count_kv` as a
per-layer *array* and Qwen's as a *scalar 4*, and never asked why two hybrids would encode
differently. The scalar is per-attention-layer; the layer typing lives in a separate key. The
clue was in front of me the same afternoon — buun's commit `context : enable fused GDN under
--split-mode tensor` touches `qwen35.cpp`, and GDN *is* gated deltanet. **Dump the full header,
not a hand-picked key list.** Both models needed `full_attention_interval` / the layer array
before any KV arithmetic was valid.

## 2b. KV precision — the §2 headline does NOT survive quantisation (corrected 2026-07-19)
*(superseded by §2c above — the Qwen column in this section is 4× too high throughout)*

§2 is computed at **f16 KV**, which I failed to state. Mark's objection is correct and is the
first thing a hacker-ish audience will say: *quantise the KV cache.* Redone across precisions
(effective bits include block scales; `turbo3~` is buun's fork and **is not available on .194's
mainline 9937 build** — projected only):

| KV type | bits | Puzzle @1M | Qwen @262k | VRAM crossover | Max ctx on a 64 GiB rig |
|---|---|---|---|---|---|
| f16 | 16.0 | 50.6 G | 90.6 G | 63,636 | Puzzle 2.61M · **Qwen 153k** |
| q8_0 | 8.5 | 46.4 G | 60.6 G | 119,786 | Puzzle 4.91M · Qwen 288k |
| q5_1 | 6.0 | 45.0 G | 50.6 G | 169,697 | Puzzle 6.95M · Qwen 408k |
| q4_0 | 4.5 | 44.2 G | **44.6 G** | 226,262 | Puzzle 9.27M · Qwen 544k |
| turbo3~ | 3.5 | 43.6 G | **40.6 G** | 290,909 | Puzzle 11.92M · Qwen 700k |

**What breaks:** the "bigger model fits in less VRAM" claim. Quantisation shrinks the KV term
while the 15 GiB weight delta stays fixed, so the crossover marches out — 64k → 291k — and at
q4_0 the two models tie, while at 3.5-bit Qwen@262k *wins* (40.6 vs 43.6 GiB). **Do not publish
the §2 headline without a precision qualifier; it is falsified at ≤4.5-bit KV.**

**What survives, and is the better claim:**

1. **The 28.4× ratio is invariant.** Quantisation scales both models identically, so Puzzle's
   per-token KV advantage is untouched by any KV scheme. Robust to every objection of this form.
2. **Precision headroom, not byte count, is the real differentiator (intended use).** At f16 on
   64 GiB, **Qwen cannot reach its own rated 262k context — it tops out at 153k.** It *requires*
   KV quantisation to be used as designed. Puzzle reaches its full rated 1M at f16 with 2.6×
   headroom to spare. Revised headline: *Puzzle-75B reaches its full rated context at full KV
   precision; Qwen3.6-27B cannot reach its own on the same rig without quantising.*
3. **Capacity headroom for practical use (RoPE-scaled, past-rated experimentation):** 17×
   at every precision tier — 2.6M vs 153k at f16, 11.9M vs 700k at 3.5-bit.

**Open risk that the whole section rests on — flag before publishing.** Puzzle's 81 SSM layers
carry a **fixed-size recurrent state, not a per-token KV cache**. §2's 9,216 B/token is the
*growing* term only; there is an unmeasured constant on top. Worse for the objection-handling:
`-ctk/-ctv` plausibly apply only to the 9 attention layers, so "just quantise the KV" may do
far less for Puzzle than the table assumes, and the Puzzle column above may be optimistic in a
way the Qwen column is not. **P-PZ1 (measured VRAM vs arithmetic, L3) is the test that catches
this, and no version of §2/§2b should be published before L3 runs.**

## 3. Correcting my own speed hypotheses (2026-07-19, owned)

This morning I measured Puzzle 10.76 t/s vs Qwen 9.53 t/s (1.13×, tight percentiles, matched
configs and clocks) against Mark's active-parameter expectation of 3×. I then offered two
mechanisms — sm_60 i-quant dequant cost, and MoE gather locality — **before reading the
architecture.** With 81 of 90 layers now known to be attention-free SSM layers, a third
candidate is more likely than either:

- **H1 (new, leading): SSM decode is latency-bound, not bandwidth-bound.** Recurrent scan layers
  carry a sequential dependency per token and cannot be widened by reading fewer bytes. A
  90-layer stack that is mostly recurrent pays depth-latency that active-parameter math does not
  model at all. Would explain why a 5.7× byte advantage yields 1.13×.
- **H2: i-quant dequantisation on sm_60 (no dp4a).** Still live; IQ4_XL vs Q8_0 is unmatched.
- **H3: MoE gather across 512 experts.** Weakened — under `-ts` layer split, a layer's experts
  are device-local, so there is no PCIe scatter. Poor cache locality remains plausible.
- **H4: 90-layer pipeline depth vs Qwen's 64** across 4 GPUs — more per-layer launch overhead.

H1 and H3 make opposite predictions under batching, which is what makes leg L2 decisive.

## 4. Test legs

- **L1 — quant isolation.** Puzzle Q4_0 vs IQ4_XL, identical serving config. Isolates H2.
- **L2 — batch sweep.** Batch 1/2/4/8 on both models. MoE gather cost (H3) amortises across a
  batch; SSM depth-latency (H1) does not. **Decisive between H1 and H3.** Also answers
  mb8565's standing question.
- **L3 — context scaling.** 4k / 16k / 64k / 131k / 262k: measure real allocated VRAM and decode
  t/s. Validates §2 empirically rather than by arithmetic, and checks whether SSM state cost
  grows where attention KV would.
- **L4 — slot scaling.** Concurrent slots to saturation at 16k each; aggregate throughput. The
  practical payoff number for the writeup.

## 5. Predictions (logged BEFORE any leg runs)

- **P-PZ1 (0.80):** Measured VRAM in L3 matches §2 arithmetic within 10% at every context point.
  *Falsified if hybrid SSM state carries a large per-token cost the KV math omits.*
- **P-PZ2 (0.70):** L2 shows Puzzle's per-token decode advantage **grows** with batch while
  Qwen's flattens — i.e. Puzzle scales better under concurrency because its bottleneck is depth,
  not bandwidth.
- **P-PZ3 (0.55):** L1 shows Q4_0 beats IQ4_XL by <15% decode. *If it beats it by more, H2 is
  the dominant story and this is a Pascal result, not a general one.*
- **P-PZ4 (0.85):** L4 exceeds 40 concurrent slots at 16k on the 64 GiB node — an order of
  magnitude past Qwen's ~9.
- **P-PZ5 (0.35, deliberately low):** Puzzle's aggregate throughput at batch 8 exceeds Qwen's
  by >2×. Stated low because single-stream results give no reason to expect it; logging it so a
  surprise is scored rather than rationalised.

## 6. Caveats to carry into any writeup

Single node, Pascal-class, no P2P, layer-split only — sm_60 lacks dp4a, so quantisation costs
here are not representative of modern cards. Quant levels are unmatched between the two models
(IQ4_XL vs Q8_0) and matching them is exactly leg L1. The 1M-context row in §2 is arithmetic,
not a measurement, until L3 runs — and it exceeds this node's 64 GiB, so it will need to be
flagged as projected or tested elsewhere.
