# Decode-path arm — does VBR damage output during generation?

Node `.73` (2× Tesla P100, sm_60, 1063 MHz / 150 W). Build `a8e5b5a38` (buun VBR fork),
`llama-server`. Model `Hermes3.6-35B-A3B-Uncensored-Genesis-V5-APEX.gguf`. Prompt drawn from
wikitext-2-raw. Date 2026-07-28.

## Why this exists

Every number in the 28-cell KV KLD panel and both headroom arms came from
`llama-perplexity`, which is teacher-forced — all prefill, no decode. buun's position:

> the dynamic degrade path is only functionally on *decode*

If that is right, every published figure is VBR's best case and the path an agent actually
runs has never been measured. The server binary carries decode-only knobs perplexity never
touches (`--vbr-reclaim-floor`, `--vbr-reset-keep-frac`), which is independent evidence the
paths differ.

**Prediction logged before the run: VBR's decode-path same-top materially worse than
prefill at matched occupancy — 65 % confidence.**

## Design

Serve at ctx 16384. f16 KV there is **320.00 MiB** (160/device, measured). VBR budget set to
**83 MiB** ≈ measured static turbo4 at that depth (82.50 MiB), floor t4. Greedy decode
(temp 0, top_k 1) from an f16 reference and from VBR on an identical prompt. Both greedy, so
they track exactly until their KV states diverge — first-divergence position is a direct
readout.

Determinism hygiene, all three known channels closed: `-np 1` (no concurrent batched
decoding, no first-use slot asymmetry), `cache_prompt=false` (no prefix-cache reuse), single
sequential request. `-sm layer` (not tensor) to avoid the parallel-reduction confound.

Degrade log lines carry the cell count they fired at, which converts directly to a sequence
position — that is what makes prefill-vs-decode attribution possible.

## Instrument validation

**f16 run 0 vs run 1: byte-identical, both passes, both arms.** The comparison floor is
exactly zero, so any divergence below is real. VBR is likewise self-identical run-to-run.
This is the determinism recipe from `PRICE_OF_DETERMINISM.md` working as specified.

## Pass 1 — prompt 2295, predict 2500 (attribution failed, result still informative)

| arm | sha | chars | predicted | tok/s |
|---|---|---|---|---|
| f16 run0 | `2069dbc6ad6f` | 7496 | 2500 | 40.30 |
| f16 run1 | `2069dbc6ad6f` | 7496 | 2500 | 40.28 |
| vbr run0 | `c3d6073c0b5f` | 11832 | 2500 | 37.25 |
| vbr run1 | `c3d6073c0b5f` | 11832 | 2500 | 37.28 |

- First token divergence: **position 76** of 2500.
- 58 degrade events at two cell positions: 1792 and 3840. Targets **turbo8 ×40, turbo4 ×18**.
- **First degrade at cell 1792 < prompt 2295 ⇒ it fired during PREFILL.** So this pass does
  not isolate the decode path; the cache was already degraded before generation began.

Design error on my part: I sized the prompt expecting the f16 entry tier to survive to
~4250 tokens (83 MiB of a 320 MiB f16 requirement). Degrades actually begin at ~1792 cells —
the controller does not run the entry tier to the budget line.

## Pass 2 — prompt 774, predict 3000 (clean decode isolation)

| arm | sha | chars | predicted | tok/s |
|---|---|---|---|---|
| f16 run0 | `d4cb9dc44b68` | 10914 | 3000 | 40.56 |
| f16 run1 | `d4cb9dc44b68` | 10914 | 3000 | 40.59 |
| vbr run0 | `d4cb9dc44b68` | 10914 | 3000 | 39.33 |
| vbr run1 | `d4cb9dc44b68` | 10914 | 3000 | 39.36 |

- 22 degrade events, all at cell 2048 = **decode position 1274 — during generation**.
- Targets: **turbo8 ×22**, no turbo4.
- **f16 and VBR output byte-identical across all 3000 tokens.**

### PREDICTION FALSIFIED

A decode-time degrade to turbo8 across 22 tensors produced **zero output change** over the
remaining ~1726 tokens. At 65 % I predicted materially worse decode-path behaviour; at
turbo8 depth the damage is not merely small, it is nil.

### The number that makes this interesting

Panel same-top for turbo8 is **98.659 %** (ctx 32768). If that per-token agreement rate
applied to greedy self-decoding, the chance of 1726 consecutive tokens matching would be
0.98659^1726 ≈ **7 × 10⁻¹¹**. It happened on the first try, twice.

So the per-token agreement measured by teacher-forced wikitext KLD **does not transfer** to
self-generated greedy decoding. The most likely reason: self-generated continuation is a
low-entropy regime — the model is following its own trajectory and top-1 margins are wide —
whereas wikitext teacher-forcing lands on many near-tied positions where a small numeric
perturbation flips the argmax.

**This inverts buun's caveat.** The concern was that prefill-only measurement flatters VBR.
On this evidence the panel is instead a *pessimistic* proxy for agentic decode: same-top on
wikitext substantially overstates divergence risk during generation.

### What separates pass 1 from pass 2

Degrade **depth**, not prefill-vs-decode. Pass 1 reached turbo4 on 18 tensors and diverged
at token 76; pass 2 only reached turbo8 and never diverged. Consistent with turbo4 being the
codec that actually moves argmax under generation, and turbo8 being benign.

## Throughput cost of the dynamic path

| pass | f16 tok/s | VBR tok/s | cost |
|---|---|---|---|
| 1 (58 degrades) | 40.30 | 37.25 | 7.6 % |
| 2 (22 degrades) | 40.56 | 39.33 | 3.0 % |

Transcoding on the side stream is cheap at these wave sizes.

## Pass 3 — prompt 774, predict 6000 (turbo4-depth degrades, all during decode)

| arm | sha | chars | predicted | tok/s |
|---|---|---|---|---|
| f16 run0 | `7e695ce6332d` | 21731 | 6000 | 40.32 |
| f16 run1 | `7e695ce6332d` | 21731 | 6000 | 40.36 |
| vbr run0 | `7e695ce6332d` | 21731 | 6000 | 37.02 |
| vbr run1 | `7e695ce6332d` | 21731 | 6000 | 36.97 |

- 58 degrade events at cells 2048 and 3840 = decode positions **1274 and 3066**, both during
  generation. Targets **turbo4 ×18, turbo8 ×40**.
- **Byte-identical to f16 across all 6000 tokens.**

This is the same degrade profile as pass 1 — 58 events, turbo4 ×18, turbo8 ×40 — which
diverged at token 76. The difference is *when the first wave landed*: prefill in pass 1,
decode in pass 3.

### Revised reading

Degrade **depth** was the pass-1/pass-2 explanation and it is now falsified: pass 3 reaches
turbo4 depth and stays byte-identical. The surviving distinction is prefill vs decode.

**Working hypothesis (not established):** a degrade during prefill corrupts cache entries
for prompt positions that generation then attends over from its very first token, when the
model is still establishing a trajectory and top-1 margins are narrow. A degrade during
decode lands when the model is deep in a self-consistent, low-entropy continuation where the
argmax is robust. Divergence risk would then be concentrated at the *start* of generation,
not distributed across it.

**Confound that blocks the conclusion:** pass 1 used a 2295-token prompt and pass 3 used 774
tokens, so they are different generation tasks. Prompt, not phase, could be the operative
variable. Pass 4 (control) holds the pass-1 prompt fixed at 2295 and raises the budget to
110 MiB so the first degrade falls past the prompt — if it then stays byte-identical, phase
is confirmed; if it diverges anyway, the prompt was doing the work.

## Pass 4 — CONTROL: pass-1 prompt held fixed, budget raised to 110 MiB

Prompt sha `9c30e255558b` — identical to pass 1, 2295 tokens evaluated. Only the budget
changed (83 → 110 MiB), which moves the first degrade past the end of the prompt.

| arm | sha | chars | predicted | tok/s |
|---|---|---|---|---|
| f16 run0 | `0141e561f0d1` | 10496 | 4000 | 40.16 |
| f16 run1 | `0141e561f0d1` | 10496 | 4000 | 40.20 |
| vbr run0 | `0141e561f0d1` | 10496 | 4000 | 37.74 |
| vbr run1 | `0141e561f0d1` | 10496 | 4000 | 37.75 |

- 36 degrade events at cells 4096 and 6144 = decode positions **1801 and 3849**, both during
  generation. Targets **turbo8 ×36**, no turbo4.
- **Byte-identical to f16 across all 4000 tokens.**

**Prompt is ruled out.** The same prompt that diverged at token 76 in pass 1 stays
byte-identical when the degrades land in decode instead of prefill. The only changed variable
is the budget, and its only effect is *where* the wave falls.

## Pass 5 — DEPTH-MATCHED CONTROL: prompt 2295, budget 110 MiB, predict 10000

At 8.125 bits a 110 MiB budget covers ~11,090 cells, so generating to 12,295 total cells
forces degradation *below* turbo8 — turbo4 depth — with every wave landing in decode.

| arm | sha | chars | predicted | tok/s |
|---|---|---|---|---|
| f16 run0 | `5fa33e45ea53` | 22496 | 10000 | 39.61 |
| f16 run1 | `5fa33e45ea53` | 22496 | 10000 | 39.61 |
| vbr run0 | `90687cef2a9c` | 22496 | 10000 | 34.13 |
| vbr run1 | `90687cef2a9c` | 22496 | 10000 | 34.11 |

- 74 degrade events across **4 waves**, cells 4096…12032, all in decode. Targets
  **turbo4 ×34, turbo8 ×40** — the deepest degradation of any pass.
- First degrade at decode position 1801. **First divergence at decode position 7613** —
  5,812 tokens and three further waves after the first degrade.

**This diverges.** Passes 2–4 did not, so "decode-phase degradation does not change output"
is withdrawn.

### Revised reading — consistent with all five passes

| pass | prompt | first wave | depth | waves | divergence |
|---|---|---|---|---|---|
| 1 | 2295 | **prefill** (cell 1792) | turbo4 ×18 | 2 | **token 76** |
| 2 | 774 | decode (pos 1274) | turbo8 ×22 | 1 | none / 3000 |
| 3 | 774 | decode (pos 1274) | turbo4 ×18 | 2 | none / 6000 |
| 4 | 2295 | decode (pos 1801) | turbo8 ×36 | 2 | none / 4000 |
| 5 | 2295 | decode (pos 1801) | turbo4 ×34 | 4 | **token 7613** |

Decode-phase degradation is **not free — it is roughly 100× more tolerant.** With the prompt
held fixed at 2295 tokens, moving the first wave from prefill to decode moves first
divergence from token 76 to token 7613. Divergence still arrives, but only after substantial
accumulated depth (34 turbo4 events across 4 waves) and thousands of tokens.

Passes 2–4 are not counter-examples to pass 5; they are the same curve sampled short. Pass 3
ran 6000 tokens with 2 waves and 18 turbo4 events — less accumulation than pass 5 had at the
point where it broke.

**Mechanism (still hypothesis):** generation attends over prefill-corrupted entries from its
very first token, when the trajectory is unsettled and top-1 margins are narrow. A
mid-generation degrade lands in a committed, low-entropy continuation where the argmax is
robust, and it takes accumulated damage to knock it off course. Not tested directly.

### Revision history of this document

This reading is the fourth. Depth was the pass-1/2 explanation (falsified by pass 3); phase
alone was the pass-3/4 explanation (falsified by pass 5). The current reading — phase sets
the *rate*, accumulated depth sets whether divergence arrives at all — is the first that fits
every pass. Recorded because the earlier two are cited in Discord messages already sent.

### Throughput cost scales with degrade count

| degrades | f16 tok/s | VBR tok/s | cost |
|---|---|---|---|
| 22 | 40.56 | 39.33 | 3.0 % |
| 58 | 40.32 | 37.02 | 8.2 % |
| 74 | 39.61 | 34.13 | 13.8 % |

### What is now established, and what is not

Established across four passes:

| pass | prompt | first wave | max depth | result |
|---|---|---|---|---|
| 1 | 2295 | **prefill** (cell 1792) | turbo4 | diverges at token 76 |
| 2 | 774 | decode (pos 1274) | turbo8 | byte-identical / 3000 |
| 3 | 774 | decode (pos 1274) | **turbo4** | byte-identical / 6000 |
| 4 | 2295 | decode (pos 1801) | turbo8 | byte-identical / 4000 |

- **Prompt is not the variable** — passes 1 and 4 share a prompt and differ only in phase.
- **Depth is not the variable** — pass 3 reaches turbo4 depth entirely in decode and does not
  diverge.
- Phase is the surviving explanation: **prefill-phase degradation changes output; decode-phase
  degradation does not**, across two prompts and up to turbo4 depth.

Not established: no single pass matches degrade *depth* across phases on the same prompt.
Pass 1 (prefill) reached turbo4; pass 4 (decode, same prompt) reached only turbo8. The
depth-independence rests on pass 3 carrying it on the other prompt. A pass at prompt 2295
with a budget that puts a turbo4-depth wave in decode would close this; the four passes
triangulate it but do not nail it in one cell.

The mechanism remains hypothesis: generation attends over prefill-corrupted entries from its
very first token, when trajectory is unsettled and top-1 margins are narrow, whereas a
mid-generation degrade lands in a committed low-entropy continuation. Not tested directly.

## buun's floor-ladder method — real, but does not bind on this rig

buun: *"you would just do --vbr-floor 6.25 and then check what it auto-calculates for max
context to know the general area."* The help text documents exactly this: `--vbr-vram-budget
auto` … *"when -c is unset, advertises n_ctx = the budget's capacity at the --vbr-floor
tier"*.

Ran floors t4 / 5.125 / 6.25 / 7.25 / t8 / 12.0 with `-c` unset, `-fit on`:

| floor | advertised n_ctx | resolved budget |
|---|---|---|
| all six | 262144 | ~3519 MiB |

Flat because `auto` resolves from **free VRAM**, which does not depend on the floor
(3518.74 MiB at t4 vs 3519.37 at t8), and 3519 MiB covers 256k context even at 8.125 bits.
`n_ctx` therefore pinned to `n_ctx_train = 262144` at every floor — the model's ceiling binds
before the tier does. The method is sound; this model/hardware pair just cannot exercise it.

### Closed form from the measured costs (answers the same question directly)

The three measured allocations fit exactly, C = 1.25 at all three points:

> **KV MiB = (n_ctx / 1024) × bits_per_value × 1.25**  (this model, 10 KV layers)

| floor | bits | max ctx @ 3519 MiB | context vs static turbo4, same memory |
|---|---|---|---|
| turbo4 / t4 | 4.125 | 699k | 100 % |
| 5.125 | 5.125 | 562k | 80 % |
| **6.25 (q6)** | 6.250 | **461k** | **66 %** |
| 7.25 | 7.250 | 398k | 57 % |
| turbo8 / t8 | 8.125 | 355k | 51 % |
| f16 | 16.000 | 180k | 26 % |

So "where q6 sits": a 6.25 bits/value floor buys 66 % of the context static turbo4 buys for
the same VRAM.

## Limits of this result

- One model, one prompt, one budget, ctx 16384. n=1 on prompt diversity.
- Pass 2's degrade wave reached only turbo8. Whether a **turbo4-depth decode degrade**
  breaks byte-identity is the open question — pass 3 (prompt 774, predict 6000) is running to
  cross the later waves at cells 3840 and beyond.
- Greedy decoding only. Sampled decoding at temperature > 0 is a different regime and is not
  measured here.

## Provenance

- `.73:/home/mark/decode-path/` — `decode_probe.py`, `run_decode_path.sh`, `compare_decode.py`
- Pass 1: `decode-path/{f16,vbr}_runs.json`, `logs/server_{f16,vbr}.log`
- Pass 2: `decode-path/isolate/`
- Pass 3: `decode-path/deep/` (in flight)
