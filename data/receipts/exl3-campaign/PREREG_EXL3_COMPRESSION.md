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
