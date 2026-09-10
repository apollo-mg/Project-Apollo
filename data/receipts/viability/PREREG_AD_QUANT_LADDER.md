# PREREG — controlled quant ladder: does abstention hold as bitrate falls?

**Written 2026-09-07 before the run.** Scored honestly, misses included.

## Why this exists

`RESULT_IQ3_GLIMPSE_MEDIUM.md` measured abstention at IQ3_XXS and found it *improved*
(23/24 vs Q6_K's 21/24, answerable 24/24 both). But that run moved **four variables at once**
— quant, GPU, backend, packager — so a result in either direction was attributable to none of
them individually (`AFM-20`). It was informative only because it held.

This is the controlled version. One box, one binary, one backend, one packager, one fixture,
same seeds. **Bitrate is the only variable.**

| arm | file | GiB |
|---|---|---:|
| L1 | `Qwen3.8-27B-AD-IQ2_XS.gguf` | 9.21 |
| L2 | `Qwen3.8-27B-AD-IQ3_XXS.gguf` | 11.25 |
| L3 | `Qwen3.8-27B-AD-IQ3_S-IQ3_XXS.gguf` | 12.09 |

Desktop RX 9070 XT (gfx1201), `buun-llama-cpp/build_rocm` `3823c9eb6`, `-ngl 99 -c 8192 -fa on`,
`--tier cal --effort medium --sampling card`, seeds 1001–1003.

**`medium` only.** The `xhigh` arm on this build aborts with `Context size has been exceeded`
— it creates 149 MiB context checkpoints the `.194` reference build does not, and xhigh's long
generations exhaust the KV cache. That is a known instrument failure, not a model property, and
it is why no xhigh arm appears here.

## What is still not controlled

- **Against the Q6_K reference**, hardware/backend/packager still differ. Comparisons *within*
  this ladder are clean; comparisons *to* `.194`'s Q6_K numbers are not.
- **AD is one packager.** A recipe that protects the tensors deciding these items would produce
  a flat ladder for a reason unrelated to bitrate.
- L2 vs L3 is a narrow bitrate step (11.25 → 12.09 GiB, ~7%). Little should be expected there.

## Predictions

| # | prediction | conf |
|---|---|---:|
| L-1 | L2 (IQ3_XXS) reproduces today's 23/24 ± 1 — the earlier result was not a fluke of the other three variables | 0.70 |
| L-2 | L1 (IQ2_XS, 9.21 GiB) abstention ≥ 19/24 — abstention survives even below the recommended range | 0.50 |
| L-3 | L1 answerable **drops below 24/24** — 2-bit costs knowledge before it costs calibration | 0.65 |
| L-4 | The ladder is **flat on abstention** (all three within 2 of each other) while answerable falls monotonically with bitrate | 0.55 |
| L-5 | `CAL-U3` is non-deterministic on at least two of the three arms (it flipped 1/3 at IQ3_XXS today, after 10/10 determinism at Q6_K) | 0.60 |

**L-3 and L-4 together are the interesting claim:** that quantisation degrades *knowledge*
before it degrades *calibration*, i.e. the model keeps knowing what it does not know after it
has stopped knowing things. If both hold, the operator's 16 GB position is stronger than a
single point could establish — the failure mode at low bitrate is a model that abstains more
because it genuinely knows less, not one that starts making things up.

**L-5 tests the mechanism.** `CAL-U3` (false premise, all entities real) was perfectly
deterministic at Q6_K and destabilised at IQ3. If abstention were a wide-margin trained habit,
U3's confident wrong retrieval should also be wide-margin and survive; that it wobbles suggests
a narrow margin perturbed by weight noise. More arms give that signal more than n=3.

## Stopping rule

3 reps × 3 arms, then score. Interim looks may trigger an abort only, never an extension.
