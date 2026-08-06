# `-fa on` costs more fidelity than quantising BF16→Q8_0 — and perplexity cannot see it

`.194`, 4× Tesla P100 (sm_60), `llama_stock/build_puzzle` @ `73a55486c` (carries the sm_60 fp32
carve-out). Puzzle-75B-A9B **Q2_K**, wikitext-2, `-c 2048 --chunks 32 -ngl 99 -sm layer
-ts 1,1,1,1`, default f16 KV. Date 2026-07-30. Predictions in `PREDICTIONS_fa_equivalence.md`.

**`-fa off` wrote the truth base; `-fa on` was scored against it. FA is the only difference.**

## Result

| metric | value |
|---|---|
| **Median KLD** | **0.000317** |
| **Same top-token** | **98.686 % ± 0.063** |
| 99.0 % KLD | 0.010092 |
| 99.9 % KLD | 0.026456 |
| Maximum KLD | 0.115554 |
| RMS Δp | 0.778 % ± 0.014 |
| Maximum Δp | 18.966 % |
| **Mean PPL(Q)/PPL(base)** | **0.999910 ± 0.000323** |

**Roughly 1 in 76 tokens changes its argmax when you flip `-fa on`.**

## Put that on the quantisation ladder

Same instrument, same corpus protocol, from `Instrument_Disagreement_PPL_vs_KLD.md`
(Qwen3.6-27B, fp32-clean sm_60 build):

| change | same-top % | median KLD |
|---|---|---|
| Q8_0 vs BF16 | 99.197 | 0.000103 |
| **`-fa on` vs `-fa off`** | **98.686** | **0.000317** |
| Q6_K vs BF16 | 98.033 | 0.000707 |
| Q5_K_M vs BF16 | 97.074 | 0.001503 |

**Toggling flash attention perturbs the model more than quantising BF16 → Q8_0, and lands
between Q8_0 and Q6_K.** An attention-implementation switch costs about as much fidelity as a
quantisation step — while being universally treated as a free speed/memory optimisation.

## Perplexity is blind to it — again

`Mean PPL(Q)/PPL(base) = 0.999910 ± 0.000323`. PPL says the two configurations are the *same
model to four decimal places*. Same-top says 1 token in 76 picks a different word.

This is the second independent confirmation of `Instrument_Disagreement_PPL_vs_KLD.md`, and on a
completely different axis — that receipt found PPL inverting a *quantisation* ladder; this finds
it blind to an *attention implementation* change. Anyone validating `-fa on` with perplexity —
which is the obvious and standard thing to do — would conclude it is free. It is not.

## Prediction scoring

| id | claim | conf | outcome |
|---|---|---|---|
| P-FA1 | not bit-identical (KLD > 0) | 0.97 | **CONFIRMED** |
| P-FA2 | median KLD < 1e-4 | 0.65 | **FALSIFIED** — 0.000317 |
| P-FA3 | same-top ≥ 99.0 % | 0.60 | **FALSIFIED** — 98.686 % |
| P-FA4 | lands in "safe to mix" band | 0.40 | **FALSIFIED** |
| P-FA5 | both passes complete | 0.90 | **CONFIRMED** |

Three of five falsified, but the hedge was right: P-FA4 was deliberately held at 0.40 because
Q2_K is the worst case for near-tie flipping, and that is exactly how it broke.

## Verdict against the pre-registered rule

The rule fixed before the run: *median KLD > 1e-4 **or** same-top < 99 % → must re-run
everything with `-fa on`.*

**Both criteria fire.** 0.000317 > 1e-4, and 98.686 % < 99 %. The ladder **cannot** mix FA
settings across rungs. The 21 hours already spent on `q2_on`/`q2_off` under `-fa off` are sunk;
keeping them is not a reason to accept a confounded ladder.

## Consequences for the ladder

`-fa off` is not a viable common setting: Q4_K_M is 48 GiB of weights and IQ4-XL 41.6 GiB, and
with FA disabled Puzzle's heterogeneous layers force V-cache padding to 256 that cost ~20 GiB —
which is precisely why both rungs OOM'd. **`-fa on` is the only setting in which every rung
loads.** So the ladder must be re-run entirely with `-fa on`.

Measured with `-fa on`, IQ4-XL at 32k ctx: **44,354 / 65,536 MiB**, decode 11.22 t/s, no
V-padding warning. Device 1 sits at **15,573 / 16,384 MiB (95 %)** — `-ts 1,1,1,1` splits by
ratio, and Puzzle's uneven layers put ~35 % of bytes on one card. Scaling that to Q4_K_M's 48 GiB
predicts ~18,250 MiB on device 1; the actual observed failure requested **18,268 MiB**. Q4_K_M
needs a hand-tuned `-ts` regardless of FA.

## Scope limits — do not over-generalise this

- Measured on **sm_60 (Pascal)**. FA kernel selection is architecture-dependent; this magnitude
  may not transfer to Ampere/Ada/RDNA. Untested.
- Measured at **Q2_K (~2.5 bpw)**, deliberately the worst case — near-ties are dense at low bpw,
  so small numerical differences flip more argmaxes. The effect is likely smaller at Q8.
- Measured on **Puzzle-75B**, a NAS architecture with heterogeneous layers and *variable V
  embedding widths across layers*. That is unusual and may interact with FA specifically.

Any of those three could be doing the work. The finding as stated — *on this hardware, this
model, this quant, `-fa on` is not free and PPL cannot detect it* — is solid. A general claim
that "flash attention costs a quant step" is **not** supported by one cell and should not be made
without an architecture and quant sweep.

## Provenance

- `~/hep/fa_kld.sh` on `.194`; local copy `scratchpad/fa_kld.sh`
- `~/hep/fa_kld/base_faoff.log`, `~/hep/fa_kld/test_faon.log`, `~/hep/fa_kld/fa_kld.log`
- Base: `~/hep/fa_kld/puzzle_q2_faoff.kld` (8.0 GB, regenerable)
- FA-on load probe: `~/hep/fa_probe.sh`, `~/hep/fa_probe_on_32768.log`
