# RESULT: the pi adapter does not ruin Hermes -- it makes it more careful: 62 of 83 argus items passed against the base's 56, almost all of the gain from asking when a request is ambiguous (19 of 30 ask items against 13); the act side is unchanged

**Prereg:** `PREREG_PI_HERMES.md` (committed before any main-run item). **Run:** 2026-11-22 19:29 to 21:34 EST (UTC
2026-11-23), `argus/run_pi_main.sh` -> `run_argus_pi.sh main`, code `d2e94644`. **Records:** `raw/` (both arms' rows,
the run log, the fixture log; home paths redacted), timing smoke in `smoke/`. **Analysis:** `analyze_pi_hermes.py`,
written after the run (the prereg fixed the pass rule, voids, unit and tests), output `summary.txt`.

Preflight on both arms through the tunnel: the Q8_0 base, temperature 0, 0 and 1 adapters, n_ctx 65,536, thinking off,
warm-up discarded. 83 of 83 items per arm, no void, no timeout. Getting there took three failed smoke launches, none of
which reached a model: a fixture-config edit that assumed the wrong endpoint, a calendar guard that could not pass
(argus snaps its world to the following Thursday), and this Hermes's refusal of models under a 64K window.

## Results (pass rule as `tools/argus_reps_compare.py`)

| | BASE | PIA (base + pi adapter) |
|---|---|---|
| all 83 items | 56 | **62** |
| act items (47) | 43 | 42 |
| ask items (30): asked instead of acting | 13 | **19** |
| answer-only items (6) | 0 | 1 |
| acted when it should have asked (WRONG-ACTION) | 15 | **7** |
| median seconds per item; backend calls per item | 65; 2.3 | 72; 2.1 |

Eight items differ: seven in the adapter's favour (six ask items where the base acted and the adapter asked, one lookup
the base never attempted) and one against it (`B-f4-unsat-r2`: the base found the Thursday review and moved it, the
adapter asked which review was meant).

## Predictions (unit = template, 43 clusters)

| | result |
|---|---|
| H1 equivalence within +/-10 pp | **not equivalent, leaning better:** +7.0 pp, 95% CI [-0.2, +14.2], 90% CI [+1.0, +13.0], sign-flip p = 0.11. The interval leaves the +10 bound, on the side of improvement |
| H2 the adapter passes FEWER ask items | **fails, the other way:** +18.8 pp on the 16 ask templates (95% CI [+2.3, +35.2], p = 0.06); six items flip from acting to asking, none back |
| H3 act side no worse than -5 pp | **holds:** -2.1 pp (one item) |

## Reading

1. **It does not ruin Hermes.** On the act side it is unchanged (42 of 47 vs 43), and overall it passes more.
2. **It asks where the base guesses.** The base acts on an ambiguous request 15 times, the adapter 7. My prediction
   was the opposite: that a model trained where nobody answers questions would never learn to ask. What carried over
   instead looks like the habit seen in the coding test -- stop and report a problem rather than push through it
   (`pi-adapter/RESULT_PI_ADAPTER.md`: 13 of 21 impossible tasks declared, base 4). In an assistant, "this can't be
   done as asked" becomes "which one do you mean?".
3. **The cost is small and of the same kind:** one item where the right move was to act and the adapter asked
   instead. A model that asks more will sometimes ask when it need not.
4. **Speed is about the same** (median 72 s vs 65 s per item), with slightly fewer backend calls.

## Limits

One run per item, greedy, thinking off; prompt cache on (single draws, the same condition for both arms); 43
templates, and the ask-side difference rests on five templates (p = 0.06); one Hermes version, an assistant corpus on
a fake mailbox and calendar; q8_0 KV at 64K (Hermes's minimum), not the f16 KV of the adapter's other runs.
