# Predictions — static TCQ tiers vs the VBR controller

**Logged 2026-08-19, before results.** Desktop RX 9070 XT (gfx1201), buun `02f8581c65`,
`Qwen3.8-27B-AD-IQ2_S`, ctx 16384, same 10 tier-2 items + canary as `f16_control.py`.

## Why this run exists

`RESULT_VBR_COLLAPSE_CONTROLLED.md` concluded "the VBR KV path" from an f16-vs-VBR control.
Re-reading the collapsed server log shows the controller had degraded to the **`turbo1_tcq`
floor — 1.25 bits/value** — and reported the degrade order exhausted. Two projection figures
in the log decode to exactly 1.25 bpv plus the 128 KiB fixed per-context overhead measured
in `RESULT_U5E_KVSIZE.md`:

| cells | 1.25 bpv | + 128 KiB | logged |
|---|---|---|---|
| 256 | 1.250 MiB | 1.375 | **1.38** |
| 512 | 2.500 MiB | 2.625 | **2.62** |

So the arm that collapsed was running a **1.25-bit KV cache**. This run asks whether the
tier alone explains it, with no VBR controller involved.

## Predictions

| # | arm | prediction | conf |
|---|---|---|---|
| C1 | `-ctk turbo1_tcq -ctv turbo1_tcq` | **collapse** (`!` spam, same signature) | 0.75 |
| C2 | `-ctk turbo3_tcq -ctv turbo3_tcq` | **clean** | 0.65 |

## What each outcome means

- **C1 collapse + C2 clean** — VBR is exonerated as a codec defect. The finding becomes
  *the auto-fit walks into a floor tier that is unusable at this model size*, which is a
  budget/fit-policy bug, not a kernel bug. The report to buun changes completely.
- **C1 clean** — the tier is fine and the VBR controller does something beyond tier
  selection. The original headline stands and the mechanism is still open.
- **both collapse** — the low-bit TCQ family is unusable on this model/backend generally.
  Largest claim of the three; would need the CUDA arm before going anywhere.

## Validity gate

Arms report measured VRAM allocation. Expected KV @16384 ctx (32,768 values/token):
`turbo1_tcq` ~80 MiB, `turbo3_tcq` ~208 MiB, f16 1024 MiB. **An arm allocating like f16
silently fell back and is reported INVALID, not clean** — the failure mode that voided an
earlier VBR campaign (`INDEX.md` C2).

---

## Result: C1 correct, C2 FALSIFIED

| arm | alloc | first collapse | correct | canary after |
|---|---|---|---|---|
| `turbo1_tcq` | 11,104 MiB | **T2-01** | 0/10 | **DEAD** |
| `turbo3_tcq` | 11,235 MiB | **T2-01** | 0/10 | **DEAD** |

Validity gate passed: 131 MiB measured delta vs 128 MiB predicted between the two tiers,
so both codecs were genuinely engaged. Neither fell back to f16.

**Outcome 3 of the three anticipated** — both tiers collapse. `vbr` is the CLI alias for
`turbo3_tcq`, so the dynamic controller is not implicated at all: the static codec collapses
the same way. `RESULT_VBR_COLLAPSE_CONTROLLED.md`'s "the VBR KV path" needs narrowing to
the TCQ codec itself, and the floor-tier hypothesis from the log is insufficient — the
nominal tier fails too.

As written above, this is the largest of the three claims and **needs the CUDA arm before
going anywhere.**

---

# Round D/E — cross-backend, D=128, no Bug A confound

`Llama-3.2-3B-Instruct-BF16` (28L, 8 kv-heads, **D=128**, BF16 weights), md5-verified
identical on both boxes. buun `02f8581c65` on both. Single GPU. ctx 16384.

Changes two things at once from the 27B run *deliberately*, because both are controls:
D=256→128 removes the Bug A confound, and IQ2_S→BF16 removes the 2-bit-weight hypothesis.

| # | arm | box | prediction | conf |
|---|---|---|---|---|
| D1 | f16 | RDNA4 | clean | 0.95 |
| D2 | `q8_0` | RDNA4 | clean | 0.90 |
| **D3** | **`turbo3_tcq`** | **RDNA4** | **clean** | **0.55** |
| D4 | `turbo1_tcq` | RDNA4 | collapse | 0.65 |
| E1 | f16 | P100/CUDA | clean | 0.95 |
| E2 | `q8_0` | P100/CUDA | clean | 0.90 |
| **E3** | **`turbo3_tcq`** | **P100/CUDA** | **clean** | **0.70** |
| E4 | `turbo1_tcq` | P100/CUDA | collapse | 0.55 |

**D3 is the pivot.** Clean → the 27B collapse requires D=256 or 2-bit weights, and the
codec is not broken in general. Collapse → TCQ is broken on RDNA4 across models.

**D3 vs E3 answers Mark's question.** Divergence = ROCm-specific, which is the outcome his
prior predicts (buun develops primarily on CUDA).

Standing caveat: `RESULT_U5B_BUUN.md` measured `turbo3_tcq` as ~2× better than `turbo3` on
CUDA/P100 — but by **teacher-forced KLD**, which cannot observe a free-generation collapse.
"Works on CUDA" is therefore not established by that receipt, and E3 is a real question.

---

## Round D/E result — NOT ROCm-specific

| KV | RDNA4 alloc | RDNA4 | P100/CUDA alloc | P100/CUDA |
|---|---:|---|---:|---|
| f16 | 8,289 | clean 9/10 | 8,291 | clean 9/10 |
| `q8_0` | 7,480 | clean 9/10 | 7,477 | clean 9/10 |
| `turbo3_tcq` | 6,880 | **clean 9/10** | 6,869 | **clean 9/10** |
| `turbo1_tcq` | 6,625 | wrong-answer | 6,645 | wrong-answer |

D3 correct (0.55), E3 correct (0.70). Backends agree within 22 MiB on every arm.

## Round F result — D=256 is NOT the trigger

`Qwen3.5-9B-Q8_0`, D=256, 8-bit weights, RDNA4: f16 / `turbo3_tcq` / `turbo1_tcq` all
**clean 10/10**. Even the 1.25 bpv floor tier is fine at D=256 when weights are 8-bit.

Remaining difference between this and the collapsing 27B: **weight quantization**
(Q8_0 vs IQ2_S), model size (32 vs 65 blocks), and packager/checkpoint.

---

# Round G — is it TCQ, or quantized KV generally?

**Never tested:** stock `q8_0` and `q4_0` KV against `Qwen3.8-27B-AD-IQ2_S` on RDNA4. Every
collapsing arm so far has been a TCQ codec; f16 is the only clean arm. If stock quantized KV
also collapses, the finding is **"quantized KV + 2-bit weights"**, which is far broader than
a turboquant issue and would not be buun's bug at all.

| # | arm | prediction | conf |
|---|---|---|---|
| G1 | `q8_0` KV, 27B IQ2_S, RDNA4 | **collapse** | 0.60 |
| G2 | `q4_0` KV, 27B IQ2_S, RDNA4 | **collapse** | 0.70 |

G1 clean → the defect is specific to the TCQ family and buun owns it.
G1 collapse → it is quantized KV generally on 2-bit weights; upstream territory, and the
whole "VBR is dangerous" framing from last night has to be rewritten as something much larger.

## Round G result — BOTH stock quant arms clean; G1 and G2 falsified

27B `AD-IQ2_S`, RDNA4: `q8_0` KV **clean 9/10**, `q4_0` KV **clean 9/10**, both `fin=stop`
throughout, canary alive after. G1 (0.60) and G2 (0.70) both falsified. Stock quantized KV
handles 2-bit weights fine; only TCQ codecs collapse.

## Round H — the last two variables, separated

`.194` ran the 27B **`UD-IQ2_M`** (unsloth, 2-bit) on a single P100/CUDA:
f16 clean 10/10, `q8_0` clean 10/10, `turbo3_tcq` **clean**.

So TCQ + 2-bit weights is fine on CUDA but collapses on RDNA4 — except the two runs differ
in **backend AND quant recipe**. `UD-IQ2_M` is now on the desktop, so one run separates them.

| # | arm | prediction | conf |
|---|---|---|---|
| H1 | `UD-IQ2_M` + `turbo3_tcq`, RDNA4 | **collapse** (→ ROCm-specific after all) | 0.60 |

H1 collapse → backend-specific; Mark's original hypothesis is reinstated for the 2-bit path.
H1 clean → the AtomicChat `AD-IQ2_S` checkpoint is uniquely implicated, not 2-bit generally,
and `gguf-label-is-not-a-spec` applies to the collapse itself.

**Note for the Bug A record:** `q8_0` symmetric at D=256 on sm_60 was **clean 10/10** here.
`RESULT_OWNERSHIP.md` recorded that arm as *collapse 3/3* on buun `a8e5b5a38`. Differences:
single GPU (vs dual), buun `02f8581c65` (vs `a8e5b5a38`), IQ2_M (vs Q6_K). Bug A may be
multi-GPU-only or may be fixed in current buun — **untested, and it needs a 2-GPU arm to say.**

---

# Round I — quant ladder on RDNA4 (desktop use-case)

Ladder from a single packager (AtomicChat), so the packaging variable is held constant.
`AD` = "Atomic Dynamic": the suffix names the quant of the two largest tensor groups,
`AD-<ffn_down>-<ffn_up>`, collapsed to one token when they match — so `AD-IQ3_S-IQ3_XXS`
is a genuine intermediate rung, not a relabel.

Rungs pulled: `AD-IQ2_XS` (9,431 MiB), `AD-IQ3_XXS` (11,516), `AD-IQ3_S-IQ3_XXS` (12,382).
`IQ4_XS` and above do not fit this card at any useful context (15,736 of 16,304 MiB leaves
nothing for KV), so the ladder brackets the low end only.

**Context drops to 4096** to fit the upper rungs. That is a changed variable, so the first
run is a control that the collapse signature survives the smaller cache.

| # | arm | prediction | conf |
|---|---|---|---|
| I0 | `AD-IQ2_S` + `turbo3_tcq` @ **ctx 4096** | **collapse** (signature survives) | 0.85 |
| I1 | `AD-IQ2_XS` + `turbo3_tcq` | collapse | 0.85 |
| I2 | `AD-IQ3_XXS` + `turbo3_tcq` | collapse | 0.55 |
| I3 | `AD-IQ3_S-IQ3_XXS` + `turbo3_tcq` | clean | 0.55 |

I0 clean would **void the whole ladder plan** — it would mean the collapse depends on cache
size and every rung would have to run at 16k, capping the ladder at `IQ3_XXS`.

Also running: **2-GPU Bug A reproduction on `.194`** — Qwen3.8-27B-Q6_K, `q8_0` symmetric,
`-sm layer`, `GGML_CUDA_ALLREDUCE=internal`, buun `02f8581c65`. Matches `RESULT_OWNERSHIP.md`
U_E exactly except for the fork commit. Collapse → Bug A is live and multi-GPU-only.
Clean → it is fixed between `a8e5b5a38` and `02f8581c65`.

## Round I results so far

| rung | weights | MiB | `turbo3_tcq` | f16 control |
|---|---|---:|---|---|
| I0 control | `AD-IQ2_S` @ ctx 4096 | 10,625 | **collapse, item 1, canary dead** | clean 9/10 |
| I1 | `AD-IQ2_XS` | 9,431 | **collapse, item 1, canary dead** | clean 9/10 |

I0 correct (0.85) — the collapse shape at ctx 4096 matches the 16k rows exactly, so the
ladder rungs are comparable. I1 correct (0.85).

---

# Round J — I-quant or 2-bit?

**Every model that has collapsed is an I-quant**: `AD-IQ2_S`, `AD-IQ2_XS`, `UD-IQ2_M`. No
2-bit **K-quant** has ever been tested. `unsloth/Qwen3.8-27B-GGUF` `UD-Q2_K_XL` (9,373 MiB)
is one, and it is also a **third independent recipe** for the "not the checkpoint" argument.

| # | arm | prediction | conf |
|---|---|---|---|
| J1 | `UD-Q2_K_XL` + `turbo3_tcq`, RDNA4 | **collapse** | 0.60 |

J1 collapse → the condition is bit depth, and it spans quant families.
J1 clean → the condition is **I-quant** 2-bit specifically, which is a much narrower and
more mechanically suggestive claim (I-quants use codebook lookups; so does TCQ).

## Reproduction hazard, recorded

`Qwen3.8-27B-UD-IQ2_M.gguf` now returns **HTTP 404** — unsloth withdrew it when Dynamic v3.0
shipped (2026-08-19). The file we measured is pinned by md5 `7ba3d070fecfd7f1324b9e08887f5b8c`
but **is no longer downloadable under that name**. Any reproduction instruction naming it is
already broken. `gguf-label-is-not-a-spec` applies to *timestamps*, not just packagers.

## Round J result — not I-quant specific

| rung | bits | family | `turbo3_tcq` | f16 |
|---|---|---|---|---|
| `UD-Q2_K_XL` | 2 | **K-quant** | **collapse, item 1** | clean 10/10 |
| `AD-IQ2_XS` | 2 | I-quant | **collapse, item 1** | clean 9/10 |
| `AD-IQ3_XXS` | **3** | I-quant | **collapse, item 1** | clean 9/10 |

I2 correct (0.55), J1 correct (0.60). The condition spans **2-bit and 3-bit**, **I-quants and
K-quants**, **three recipes from two packagers**. "2-bit weights" was the wrong label and has
been corrected in the receipt and the published map.

`AD-IQ3_S-IQ3_XXS` (12,382 MiB) failed to load — 8-line server log ending at "loading model",
with **9 GB of host RAM available against a 12.4 GiB file**. Probable system-RAM exhaustion,
not VRAM. Retest when the desktop is quieter.

---

# Round K — the confound the ladder cannot resolve

**No Qwen3.8-27B has ever run clean with TCQ at any weight precision.** Every clean TCQ arm
on gfx1201 is the *9B*. So "low-bit weights" and "this model" are still entangled: the ladder
only walked the low end, and a 6- or 8-bit 27B does not fit this card at any useful context.

The separator is therefore the **other** direction — a **low-bit 9B**.
`unsloth/Qwen3.5-9B-GGUF` `UD-Q2_K_XL`, 3,930 MiB, same D=256 hybrid architecture as the 27B,
same packager and family as the `UD-Q2_K_XL` 27B rung that collapsed.

| # | arm | prediction | conf |
|---|---|---|---|
| K1 | Qwen3.5-9B `UD-Q2_K_XL` + `turbo3_tcq`, gfx1201 | **collapse** | 0.70 |

K1 collapse → **weight precision is the driver**, confirmed on two model sizes, and the
"low-bit weights" framing is correct.
K1 clean → the 27B is implicated specifically and the ladder's whole reading is wrong: it
would mean every rung failed because of the *model*, and precision was a spurious correlate.

## Round K result — K1 FALSIFIED, and it overturns the ladder

Qwen3.5-9B `UD-Q2_K_XL` (2-bit, D=256, gfx1201): `turbo3_tcq` **clean 10/10**, f16 clean 10/10.

**Same packager, same quant family, same bit depth, same architecture, same binary — the 27B
collapses and the 9B does not.** Weight precision is NOT the driver. The ladder's apparent
precision gradient was a spurious correlate: every rung was the same model.

## Round L — the gate hypothesis

Sorting every model tested by GQA ratio separates the results perfectly:

| model | heads / kv | GQA | result |
|---|---|---|---|
| Llama-3.2-3B | 24 / 8 | 3:1 | clean (both backends) |
| Qwen3.5-9B | 16 / 4 | 4:1 | clean (2-bit and 8-bit) |
| **Qwen3.8-27B** | **24 / 4** | **6:1** | **collapse, every quant** |
| poshih #311 (RTX 3090) | 16 / 2 | **8:1** | **corruption, reports K auto-upgraded to q8_0** |

`TURBO_AUTO_ASYMMETRIC` fires at **GQA ≥ 6**, silently rewriting K to `q8_0`. So the collapsing
runs may never have been symmetric TCQ at all — they may have been a **mixed `q8_0`-K +
TCQ-V** cache, which is also exactly poshih's configuration.

| # | arm | prediction | conf |
|---|---|---|---|
| L1 | 27B `AD-IQ2_S` + `turbo3_tcq`, **`TURBO_AUTO_ASYMMETRIC=0`** | **clean** | 0.65 |

L1 clean → the defect is the **auto-asymmetric gate's mixed pair**, not weight precision, not
the model, and not the TCQ codec in symmetric use. It would unify our result with #311 and
change who the report goes to and what it says.
L1 collapse → the gate is innocent and the 27B is implicated for some other reason.

## Round L result — gate hypothesis FALSIFIED for our build, on two grounds

1. **`TURBO_AUTO_ASYMMETRIC` does not exist in buun's fork.** It lives in TheTom's tree at
   `src/llama-kv-cache.cpp:136`. The env var was inert; L1 tests nothing on this binary.
2. **The recorded allocations already showed K was never rewritten.** `turbo1_tcq` vs
   `turbo3_tcq` on the 27B differed by **131 MiB**, matching the **128 MiB** predicted for a
   symmetric change, not the **64 MiB** predicted if K were pinned to `q8_0`. Our cache was
   genuinely symmetric TCQ.

The VRAM instrumentation was added to catch silent f16 fallback; it answered a mechanism
question it was never designed for. The GQA ≥ 6 correlation survives — the *explanation* does
not, at least for buun's fork. It may still be the mechanism in TheTom's fork for #311.

---

# Round M — is it GQA 6:1, or is it Qwen3.8-27B?

Every collapsing arm so far is the same base model. `Ternary-Bonsai-27B-Q2_g64` is
**GQA 6:1, D=256, 7,233 MiB** — a different base model with a completely different
quantization scheme (ternary), and small enough to avoid the host-RAM ceiling that killed
`AD-IQ3_S-IQ3_XXS`.

| # | arm | prediction | conf |
|---|---|---|---|
| M1 | Ternary-Bonsai-27B `Q2_g64` + `turbo3_tcq`, gfx1201 | **collapse** | 0.70 |

M1 collapse → the discriminator is architectural (GQA 6:1 / this model class), not the
Qwen3.8 checkpoint, and not weight precision.
M1 clean → Qwen3.8-27B is implicated specifically and GQA is a coincidence across four models.

## Round M result — architectural, not the checkpoint

Ternary-Bonsai-27B `Q2_g64` (GQA 6:1, D=256, ternary, different base model):
`turbo3_tcq` **collapse at item 1, canary dead, 0/10**; f16 **clean 10/10**. M1 correct (0.70).

---

# Round N — GQA, or cache size, or layer count?

Across the four models tested, **GQA ratio covaries perfectly with full-attention layer count
and with KV values/token**, so the matrix cannot separate them:

| model | GQA | full-attn layers | KV values/token |
|---|---|---|---|
| Llama-3.2-3B | 3:1 | 28 | 114,688 |
| Qwen3.5-9B | 4:1 | **8** | **16,384** |
| Qwen3.8-27B | **6:1** | **16** | **32,768** |

The published artifact leads with GQA. That is the one a maintainer can act on — and if the
real driver is cache size or layer count, it points at the wrong file.

**Cache size is separable right now.** The 27B collapsed at ctx 4096 → 32,768 × 4,096 =
**134M values**. The 9B at ctx 16384 → 16,384 × 16,384 = **268M values**, twice as many,
with GQA unchanged at 4:1.

| # | arm | prediction | conf |
|---|---|---|---|
| N1a | Qwen3.5-9B `UD-Q2_K_XL` + `turbo3_tcq` @ ctx **16384** | clean | 0.80 |
| N1b | same @ ctx **32768** (536M values, 4× the collapsing arm) | clean | 0.75 |

Both clean → **total cache size is ruled out**; GQA and layer count survive.
Either collapses → the GQA headline is wrong and the artifact must be rewritten a third time.

Note this is not the earlier depth probe, which used the 3B at D=128 / GQA 3:1 — a different
model on the clean side of every threshold.

## Round N result — cache size ruled out; GQA is the only monotonic separator

9B `UD-Q2_K_XL`, GQA 4:1, `turbo3_tcq`: **clean 10/10 at ctx 16384 and again at ctx 32768**.
N1a (0.80) and N1b (0.75) both correct. The 32k arm carries **536M cache values — 4× the
134M in the collapsing 27B arm** — with no degradation.

| model | GQA | full-attn layers | KV values/token | max cache tested | result |
|---|---|---|---|---|---|
| Llama-3.2-3B | 3:1 | 28 | 57,344 | **3,758M** | clean |
| Qwen3.5-9B | 4:1 | 8 | 16,384 | 537M | clean |
| Qwen3.8-27B | **6:1** | 16 | 32,768 | 134M | **COLLAPSE** |
| Ternary-Bonsai-27B | **6:1** | 16 | 32,768 | 134M | **COLLAPSE** |

| candidate | monotonic? | why not |
|---|---|---|
| **GQA ratio** | **YES** | 3:1 and 4:1 clean, 6:1 collapses |
| full-attention layer count | no | 28 clean **>** 16 collapse |
| KV values/token | no | 57,344 clean **>** 32,768 collapse |
| total cache values | no | 3,758M clean **≫** 134M collapse |

The Llama-3.2-3B row carries this: it is **larger than the collapsing 27B on every metric
except GQA** and it runs clean on both backends. Of the four candidates the matrix admits,
only the head ratio survives.

---

# Round O — is it TCQ, and is asymmetric actually safe?

Two gaps in everything above, both load-bearing for the proposed fix ("degrade V one step
below K everywhere except the f16 ceiling"):

1. **Every collapsing arm used a TCQ codec** (`turbo3_tcq`, `turbo1_tcq`). No **non-TCQ**
   turbo has been run symmetric on gfx1201. If `turbo4` symmetric also collapses, the
   condition is "symmetric turbo", not "symmetric TCQ".
2. **No asymmetric pair has ever been tested on gfx1201.** The proposed fix assumes
   asymmetry is safe there. The only asymmetric datum in this whole investigation is
   `turboquant#311` — `q8_0` K + `turbo4` V — which **corrupts** on an RTX 3090 at GQA 8:1.

All arms on `Qwen3.8-27B-AD-IQ2_S` (GQA 6:1), gfx1201, ctx 4096 — the configuration that
collapses at item 1 with 100% reliability across five quants.

| # | arm | tests | prediction | conf |
|---|---|---|---|---|
| O1 | `turbo4` + `turbo4` (non-TCQ, symmetric) | is it TCQ-specific? | collapse | 0.55 |
| O2 | `q8_0` K + `turbo3_tcq` V | is asymmetry the fix? | **clean** | 0.60 |
| O3 | `turbo8` K + `turbo4` V (buun's daily pair) | does the shipped pair survive? | clean | 0.70 |

O1 collapse → the fix must avoid **all** symmetric turbo at GQA ≥ 6, not just TCQ.
O2 clean → the proposed fix is sound on this hardware and worth sending.
O2 collapse → **the fix does not work**, and it would have shipped as a guess.

## Round O results — it is not TCQ, and asymmetry does not fix it

| arm | K | V | TCQ? | result |
|---|---|---|---|---|
| O1 | `turbo4` | `turbo4` | **no** | **COLLAPSE item 1** |
| O2 | `q8_0` | `turbo3_tcq` | V only | **COLLAPSE item 1** |

O1 correct (0.55) — a **non-TCQ** turbo collapses, so "TCQ" was wrong; the condition is any
symmetric turbo. O2 **falsified** (0.60) — the proposed fix, `q8_0` K with a degraded V,
collapses too. **Asymmetry is not a fix.** That is also poshih's exact shape in
`turboquant#311`, which strengthens the case that it is the same bug.

# Round P — no TCQ anywhere

| # | arm | K | V | prediction | conf |
|---|---|---|---|---|---|
| P1 | `q8_0:turbo4` | stock | classic | **collapse** | 0.75 |
| P2 | `q8_0:turbo8` | stock | classic, gentlest | collapse | 0.65 |
| P3 | `turbo8:turbo8` | classic | classic, symmetric | collapse | 0.70 |

P1 is poshih's pair exactly. All three collapsing → **any turbo codec on either side kills
GQA ≥ 6 on gfx1201**, which would make turboquant unusable for this model class on RDNA4 and
is a far larger claim than anything published so far. Any one clean → that pair is the
workaround, and it is worth sending.

## Round P results — every turbo configuration collapses; only stock KV survives

| arm | K | V | result |
|---|---|---|---|
| P1 | `q8_0` | `turbo4` | **COLLAPSE** — poshih's exact pair |
| P2 | `q8_0` | `turbo8` | **COLLAPSE** — gentlest codec, 8.125 bpv, V side only |
| P3 | `turbo8` | `turbo8` | **COLLAPSE** |

P1 (0.75), P2 (0.65), P3 (0.70) all correct. Combined with O1–O3 and the earlier rounds,
**eight of eight turbo configurations collapse and three of three stock configurations are
clean** on Qwen3.8-27B at GQA 6:1 on gfx1201.

### Full KV matrix, Qwen3.8-27B (GQA 6:1), gfx1201, ctx 4096

| K | V | any turbo? | result |
|---|---|---|---|
| f16 | f16 | no | **clean 10/10** |
| `q8_0` | `q8_0` | no | **clean 9/10** |
| `q4_0` | `q4_0` | no | **clean 9/10** |
| `turbo8` | `turbo8` | yes | COLLAPSE |
| `turbo4` | `turbo4` | yes | COLLAPSE |
| `turbo3_tcq` | `turbo3_tcq` | yes | COLLAPSE |
| `turbo1_tcq` | `turbo1_tcq` | yes | COLLAPSE |
| `turbo8` | `turbo4` | yes | COLLAPSE |
| `turbo4` | `turbo3_tcq` | yes | COLLAPSE |
| `q8_0` | `turbo8` | yes | COLLAPSE |
| `q8_0` | `turbo4` | yes | COLLAPSE |
| `q8_0` | `turbo3_tcq` | yes | COLLAPSE |

**One turbo tensor anywhere in the cache is sufficient.** Bit depth is irrelevant — `turbo8`
at 8.125 bpv fails exactly like `turbo1_tcq` at 1.25. TCQ vs classic is irrelevant. Which
side carries it is irrelevant.

**Consequence: on gfx1201, the turboquant KV cache is unusable for GQA ≥ 6 models.** Not
degraded — degenerate, from the first request, permanently. `Qwen3.5-9B` at GQA 4:1 runs the
same codecs clean at 32k context, so this is scoped to the model class, not the card.

## Round Q — VOID, not a result

`-fa off` with `turbo4` on the 27B collapsed identically. **The flag was silently overridden:**

```
W llama_init_from_model: turbo/VBR KV cache requires flash attention — enabling automatically
```

Flash attention was on for the entire arm. This tests nothing, and the hypothesis that the
defect lives in the WMMA flash-attention turbo path is **untested, not falsified**. `AFM-19`
applies — an inert knob produces a perfect-looking null. Caught only because the manipulation
was checked against the server log rather than assumed.

**One real fact does fall out:** turbo KV *cannot* be run without flash attention on this
build, so `-fa off` is not available as a user workaround. The FA-path question is
source-level and cannot be reached from userspace here.

### Remaining testable gaps, in order of value to a maintainer

1. **Token threshold.** A 256-token canary passes; a 3072-token generation kills the server.
   Never bisected. This is what turns a 10 GB model plus a fixture into "generate N tokens".
2. **Prefill vs decode.** Long prompt + short generation, never run. Halves the search space.
3. **Non-Qwen GQA ≥ 6 model.** Separates the head ratio from the Qwen-27B architecture class.
   Nothing suitable on disk.
4. **Slot count / `--kv-unified`.** All arms ran 4 slots unified. Untested at 1 slot.
