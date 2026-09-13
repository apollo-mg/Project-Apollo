# Prereg — the GGUF ladder's served speed, to finish the decision table (EXL3 campaign, test 7, ledger O5)

**Written 2026-09-12 ~18:55, before any data.** **Not launched without Mark's go-ahead:** it needs about
15 minutes on `.73`.

## Question

Test 3 measured KLD across a GGUF ladder; test 1 measured served speed for only two of those options.
The decision table therefore has holes exactly where the interesting choices are:

| option | peak VRAM (test 3) | mean KLD (test 3) | served decode (test 1) |
|---|---|---|---|
| EXL3 4.00bpw | 13,468 MiB | 0.012002 | 13.08 t/s |
| UD-IQ4_XS | 13,500 MiB | 0.015727 | **unmeasured** |
| UD-Q4_K_M | 15,448 MiB | 0.007840 | **unmeasured** |
| Q6_K, the daily driver | 21,276 MiB | 0.002770 | 20.25 t/s |

**If Q4_K_M is both faster than EXL3 and closer to the reference for 2 GB more, the campaign's answer for
this fleet is "run Q4_K_M", not EXL3.** That is worth knowing before anyone recommends a switch.

## Setup

- **Node:** `.73`, both P100s, proxy paused with a dead-man, orchestrated behind any running test.
- **Identical to test 1** in every respect except the weights: the QUAL binary (buun `9ae8f0f40` + e8m0
  guard), the daily driver's exact flags (MTP at `--draft-max 3`, the F16 mmproj, VBR KV at 262,144,
  `-sm tensor`), port 8190.
- **Arms:** `G4s` = UD-IQ4_XS, `G5s` = UD-Q4_K_M. Both are already on `.73` at `/mnt/HDD/kld/`, hash-
  verified there against their published sha256 during test 3.
- **Stages per arm, exactly test 1's:** load, fact, vision probe, 3 × 256 greedy tokens, 3 × 256 at the
  served sampling (seeds 11/12/13), and the two-step prefill.

## Predictions

| id | prediction |
|---|---|
| P-G1 | Both arms load with the daily driver's flags and read the vision probe |
| P-G2 | Both GGUFs decode faster than EXL3's 13.08 t/s at the served sampling — the format's speed penalty is not size-dependent |
| P-G3 | UD-IQ4_XS decodes faster than UD-Q4_K_M, being smaller |
| P-G4 | Both GGUF arms gain more than 1.4× from MTP, unlike EXL3's 1.24×, measured as greedy decode against test 1's MTP-off Q6_K figure scaled by size — **descriptive only**, since no MTP-off arm runs here |
| P-G5 | UD-Q4_K_M decodes faster than EXL3 **and** has lower KLD (test 3), i.e. it dominates EXL3 outright at +2 GB |

## Declared in advance

- **Speed is compared against test 1's numbers,** measured on the same node, binary, flags and prompt
  earlier the same day. That is a cross-run comparison, and `.73` has since served four other tests.
- **P-G4 has no MTP-off arm here** and is descriptive; a matched MTP-off pair would double the runtime.
- **One prompt, 256 tokens, three reps** — a speed estimate, as in test 1.
- **This measures the ladder as published by unsloth**, whose recipes differ per upload.

**Driver:** `exl3_ladder_speed.py`, committed before the run. **Scorer:** `tools/score_exl3_ladder.py`.

## Amendment 1 — 2026-09-12 ~19:50, before any data: add the EXL3 5.00bpw arm

**Test 3's Amendment 2 changed what this test is for.** EXL3 5.00bpw reads KLD 0.003994 at 16,372 MiB —
within 1.4× of the daily driver's fidelity on 4.9 GB less VRAM — so **it, not EXL3 4.00bpw, is the
configuration the quality result points at. Its speed has never been measured.** Recommending it on one
axis would repeat exactly the error Mark caught.

**New arm:** `E5s` = EXL3 5.00bpw (`/mnt/HDD/exl3/Qwen3.8-27B-exl3-5.00bpw`, pinned `a35e75a7`, verified
on `.73`). Same flags and stages as the others. Run order: `E5s`, `G4s`, `G5s`.

| id | prediction |
|---|---|
| P-G6 | E5s decodes slower than EXL3 4.00bpw's 13.08 t/s — more bits, more bytes per token |
| P-G7 | G5s decodes faster than E5s, at comparable VRAM (15,448 vs 16,372 MiB) |
| P-G8 | **No EXL3 arm beats a GGUF on both axes at once.** For each EXL3 arm there is a GGUF that is either faster at equal-or-better KLD, or closer at equal-or-better speed. Falsified if any EXL3 arm dominates every GGUF arm on speed *and* KLD together |

**P-G5 is restated for clarity:** it asked whether UD-Q4_K_M dominates EXL3 outright. Test 3 already
settled the KLD half in EXL3's favour at matched size, so P-G5 now turns on speed alone and is scored as
written against **EXL3 4.00bpw**, the arm it was written about.

**Declared:** the two GGUF arms' KLD comes from test 3, measured at `-ub 8` under `-sm layer`, while speed
here is measured under the daily driver's `-sm tensor` with VBR KV. **The two axes come from different
configurations** and the receipt must say so wherever it puts them in one table.
