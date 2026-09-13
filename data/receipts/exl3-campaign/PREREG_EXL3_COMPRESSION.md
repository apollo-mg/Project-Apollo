# Prereg — the compression frontier: is EXL3 superior compression at the sizes that matter? (EXL3 campaign, test 10, ledger O6)

**Written 2026-09-13 ~11:00, before any data.** Mark's framing: *"we would certainly need to show a
substantial difference in usable quality in order to justify it… I am actually quite interested in form
of superior compression."*

## The question

Every quality measurement so far sits at **3–6.5 bits**, where the campaign's live question was speed.
**The compression claim lives at the low end**, and we have never looked there. If EXL3 at 2.5 bpw matches
a GGUF two gigabytes larger, that is compression worth having — it is the difference between a model
fitting a 16 GB card and not.

This test builds **one quality-versus-size curve per format** across roughly 9–23 GB, by adding six arms
to test 3's five existing points.

## Setup

- **Node `.73`**, both P100s, wake proxy paused with a dead-man, orchestrated.
- **Binary: the same one test 3 used** — `~/buun-sm60-qual/build_sm60qual` (buun `9ae8f0f40` + our e8m0
  guard). **Deliberate:** test 3's five points were measured there, and a curve whose points come from two
  builds is not a curve. The freshly built `da458765d` tree is bridged instead, see P-C0.
- **Reference:** the same `/mnt/HDD/kld/ref.kld` on `.73` (Q8_0 @ `4ca72078`), so every point in this
  campaign shares one reference.
- **Flags, identical to test 3:** `-ngl 99 -sm layer -c 512 -b 512 -ub 8 --chunks 40 -fa on -ctk f16 -ctv f16`.

| new arm | file | size on disk |
|---|---|---|
| **E25** | turboderp EXL3 2.50bpw, pinned `0cd10912` | 12.32 GB |
| **E30** | turboderp EXL3 3.00bpw, pinned `6fe61ad6` | 13.82 GB |
| **E35** | turboderp EXL3 3.50bpw, pinned `8351c54e` | 15.34 GB |
| **G2x** | `Qwen3.8-27B-AD-IQ2_XS.gguf` | 9.89 GB |
| **G3xx** | `Qwen3.8-27B-AD-IQ3_XXS.gguf` | 12.08 GB |
| **G3m** | `Qwen3.8-27B.i1-IQ3_M.gguf` | 12.76 GB |
| **BRIDGE** | E30 again, on the **`da458765d`** build | — |

**Joined with test 3:** EXL3 4.00 and 5.00bpw, UD-IQ4_XS, UD-Q4_K_M and Q6_K — ten points in total.

**Size is GPU-resident bytes**, measured as peak VRAM during each run, as in test 3. Disk size overstates
EXL3's footprint (it carries a bf16 embedding table and a vision tower that never reach the card).

## Predictions

| id | prediction |
|---|---|
| P-C0 | **Bridge/gate.** The BRIDGE arm's mean KLD matches E30's on the old build within the summed uncertainties. If it does not, the two builds are not numerically interchangeable and every cross-build comparison in this campaign needs re-checking |
| P-C1 | EXL3's curve lies **below** GGUF's across the measured range — at every EXL3 point, the GGUF curve interpolated to that VRAM has higher mean KLD |
| P-C2 | **The advantage widens as size falls:** the log-KLD gap at ~10 GB exceeds the gap at ~15 GB |
| P-C3 | **E25 beats the GGUF nearest its size** (G2x, the only sub-10 GB arm) |
| P-C4 | **The compression claim, in its strongest falsifiable form: EXL3 3.00bpw is closer to the reference than a GGUF ~1.8 GB larger** (G3xx at 12.08 GB) |

**TIE rule as in test 3:** two mean KLDs differing by less than the sum of their reported uncertainties
score TIE, not confirmed or falsified.

## Declared in advance

- **This measures distribution, not usable quality.** KLD cannot say whether code compiles or a tool call
  parses. **If the curve favours EXL3, the follow-up that earns the word "usable" is a task benchmark at
  matched size** — hours, and worth spending only on that evidence.
- **Three GGUF recipes, one EXL3 quantizer.** AD-*, i1-* and UD-* come from different packagers with
  different imatrix and recipe choices, so the GGUF "curve" is a curve through *the GGUFs people
  actually download*, not through one method. That is the honest comparison for a user choosing a file,
  and it is not a controlled comparison of algorithms.
- **Provenance:** the three EXL3 snapshots are hash-verified against their published sums; `AD-IQ2_XS`,
  `AD-IQ3_XXS` and `i1-IQ3_M` are local files without recorded published hashes — **the same exception
  declared in test 9**, and they are size-checked only.
- **`-ub 8` measures the decode kernels**, as in test 3.
- **Runtime:** about 2.5–3 hours of `.73`, unattended, plus ~64 GB of transfers. The dev-diary ledger
  loses every hour the proxy is paused.

**Driver:** test 3's `exl3_kld_arm.py`, one invocation per arm, appending to the same `results.jsonl`.
**Scorer:** `tools/score_exl3_compression.py`, committed with this prereg.

---

## Amendment 1 — 2026-09-13 ~11:10, before any arm runs

Mark, mid-setup, pointed at the sub-3-bit region of a published EXL3/GGUF chart: *"I find this region
particularly interesting. You can get 3 bpw in the same space as UD-Q2 XL."* Three changes follow, all
made before a single arm has run.

### 1. Two unsloth arms added, so the low end has a *controlled* GGUF curve

The original six arms draw the GGUF side from three packagers (AD-, i1-, UD-). Both files below are
already on the control plane, so this costs transfer and ~30 min, not a download.

| new arm | file | size on disk |
|---|---|---|
| **G2u** | `Qwen3.8-27B-UD-Q2_K_XL.gguf` | 9.83 GB |
| **G3u** | `Qwen3.8-27B-UD-IQ3_XXS.gguf` | 11.91 GB |

With test 3's `UD-IQ4_XS` and `UD-Q4_K_M`, the unsloth **UD-** recipe now has **four** points spanning
9.83 → ~17 GB, bracketing E25, E30 and E35. **P-C1 and P-C2 are therefore scored twice**: once against
the all-packagers curve (the file a user actually picks) and once against the UD-only curve (one
packager, one dynamic recipe). Both are reported; **the UD-only result is the one the campaign will
quote**, because it is the closer thing to a controlled comparison. Nine arms, ~4 h; the dead-man goes
to 420 min so it cannot fire mid-arm and corrupt a `peak_mib`.

### 2. The curves are scored as **lower envelopes**, not polylines through every point

Two arms now sit ~60 MiB apart (G2u 9.83 GB, G2x 9.89 GB) with different KLD. A polyline through both
has a near-vertical segment, and `inverse()` would return a VRAM from inside that sliver for a wide
range of targets — the headline exchange-rate number would be noise. **Both curves are reduced to their
lower envelope** (walking ascending VRAM, keep a point only if it beats every smaller point) before any
interpolation.

This is deliberately **conservative for EXL3**: it gives GGUF its best possible showing at every size,
so a confirmed P-C1 is a stronger claim than it would have been. **Dominated points are listed in the
receipt rather than hidden** — "recipe X at 12.8 GB is beaten by recipe Y at 12.1 GB" is itself a
finding, and it is the honest form of the three-packagers caveat declared above.

### 3. P-C2's span is declared in advance, because E25 may not be bracketed

E25 is 12.32 GB on disk but ~3.46 GB of that (bf16 embeddings, vision tower) never reaches the card, so
its peak VRAM may fall **below the smallest GGUF arm**. If it does, it has no GGUF to interpolate
against and silently leaves the comparison — which would turn P-C2 from "~10 GB vs ~15 GB" into
"E30 vs E35" with no gate. **Declared now:** P-C2 is scored across whatever span remains bracketed, and
**the scorer prints every EXL3 point it excluded and why**. An unbracketed E25 is reported as a result
(EXL3 reaches a size GGUF does not), not silently dropped.

### 4. What the EXL3 side actually is, recorded before the numbers exist

Read from each snapshot's `config.json`. All five EXL3 points are **one series**, identical but for `bits`:

```
quant_method exl3 | version 1.4.2 | head_bits 6 | out_scales always
codebook mul1 | mtp_bits 4 | calibration 250 rows x 2048 cols
```

**Why this is recorded:** the chart Mark sent plots plain `3.00 bpw` (0.0337) and `3.00 bpw H4` (0.0257)
as **different series ~30% apart at the same nominal bitrate**. Our arms are the **H6** series
throughout. Any comparison to a published chart must name the series, and **our absolute KLD is not
comparable to that chart's in any case** — different reference (Q8_0 @ `4ca72078`, not bf16), different
corpus, 40 chunks. What transfers is the *shape* of our own curve and whether the crossover reproduces.

**Also noted:** the EXL3 side is a controlled series from one quantizer; the GGUF side is not. That
asymmetry favours EXL3 in presentation and is why change 2 hands GGUF its envelope.

### 5. O11 is retired

The clean `da458765d` worktree on `.73` — `git status` empty, **no e8m0 guard patch** — built on CUDA
12.4 with `BUILD EXIT 0`. buun's `86eae269c` replaces our local patch. **P-O11a CONFIRMED.** P-O11b
(his EXL3 unit tests on sm_60) is now run **inside this orchestration**, right after the GPUs clear, and
is **recorded but non-blocking**: the six main arms use the old `9ae8f0f40` build, so a test failure
would qualify BRIDGE's interpretation, not invalidate the curve. A `ctest` exit of 0 is **not** taken as
a pass — "no tests found" also exits 0 — so the gate asserts **4 tests ran**, and anything else is
recorded as NOT RUN.
