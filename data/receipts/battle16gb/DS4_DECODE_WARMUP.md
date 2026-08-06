# The published 2.16 t/s DS4 decode rate is a cold-cache artifact — warm steady-state is 4.75 t/s, 2.2× higher

`.194`, 4× Tesla P100-PCIE-16GB, **1063 MHz / 150 W** (verified at load). DS4-Flash UD-IQ1_S
82.5 GB, `-c 8192 -ngl 99 -sm layer -ts 3,4,4,1 -fit off -fa on -ncmoe 40`.
Build `331981025` (`version: 10260`). Date 2026-08-02.

**This started as a suspected regression and ended as a correction to our own published number.**

## The measurement

Three identical draws, **same server process**, same prompt, `cache_prompt` disabled:

| draw | decode | output |
|---|---|---|
| 1 | **1.74 t/s** | gzip 0.4743, 972 chars |
| 2 | **4.21 t/s** | gzip 0.4743, 972 chars |
| 3 | **4.75 t/s** | gzip 0.4743, 972 chars |

**Decode rises 2.7× across three identical requests.** Output is byte-stable throughout — the
model is doing exactly the same work; only the machine's state changes.

Mechanism: with `-ncmoe 40` the routed experts live in CPU memory and are read on **every
token**. The first generation faults them in from disk; later ones hit page cache. Nothing
about this is model behaviour.

## The correction

`DS4_FLASH_P100_LOAD.md` headlines **2.16 t/s** and builds its practical read on it
("at 2.16 t/s a 400-token answer takes ~3 minutes"). That number came from
`~/ds4_ts/server_n40_ts_bal.log`, produced by `ds4_ts_tune.sh` — a script that **loads a fresh
server per configuration and generates exactly once**.

So every historical DS4 decode figure on this fleet is a **cold first draw**:

| source | tokens | decode | state |
|---|---|---|---|
| `ds4_sweep/server_ncmoe40.log` | 200 | 2.13 t/s | cold, 1st gen of process |
| `ds4_ts/server_n40_ts_bal.log` | 200 | **2.16 t/s** ← published | cold, 1st gen of process |
| `ds4_probe` | 400 | 3.19 t/s | cold, but longer gen amortises warming |
| today, draw 1 | 200 | 1.82 / 1.74 t/s | cold |
| today, draws 2–3 | 200 | **4.21 / 4.75 t/s** | **warm** |

The 400-token probe landing at 3.19 t/s — between the cold 200-token figures and the warm
ones — is consistent: a longer generation spends more of its life warm, so it averages higher.
**Generation length and cache state both move this number**, which means no single decode
figure characterises this configuration.

**Corrected statement:** DS4-Flash IQ1_S on 4×P100 at `-ncmoe 40` decodes at **~1.7–1.8 t/s
cold and ~4.2–4.8 t/s warm**. Quote the warm figure for sustained use, the cold figure for
first-response latency, and never a single number without saying which.

## Consequences for other receipts

- `DS4_FLASH_P100_LOAD.md` — 2.16 t/s headline and the "~3 minutes for 400 tokens" read are
  cold-state figures. Warm: a 400-token answer is ~85 s, not ~185 s.
- `DS4_PROMPTCACHE_LONGCTX.md` — the corrected per-turn estimate used 2.16 t/s for decode. At
  the warm rate a 300-token answer is ~63 s, not ~139 s, so a cached turn is **~1.7 min**
  rather than ~3 min, and an uncached turn ~9.6 min rather than ~11 min. The *conclusion* is
  unchanged and in fact strengthened: caching removes the ~8.5-minute prefill and leaves you
  decode-bound at a lower cost than stated.
- The `PREDICTIONS_ds4_flash_p100.md` scoring of **P-D3 (decode 1–6 t/s, CONFIRMED)** survives
  — the interval was wide enough to contain both states.

## How this nearly became a false regression report

Build `331981025` merged the Laguna port, including `4330be608 cuda: sum MoE expert outputs on
decode (n_tokens==1)` — decode-path MoE summation, precisely DS4's hot path here. A K=1 check
read **2.20 → 1.82 t/s (−17 %)** with **byte-identical VRAM placement**, which is exactly the
signature of a compute-path regression rather than a layout change. The mechanism was named,
plausible, and wrong.

Two things stopped it being sent to Tom:

1. **Refusing to report a regression from one draw.** K=3 was run first, and it dissolved the
   effect immediately.
2. Even so, **the parser was wrong**: the regex `eval time =` also matches
   `prompt eval time =`, so per-draw values interleaved prefill and decode
   (printed 0.66 / 1.74 / 3.07 — meaningless). The real decode rates were only visible in the
   raw ordered lines. **A K=3 run with a broken parser would have produced a different wrong
   answer, not a right one.**

The irony worth recording: **this exact confound was identified hours earlier** in
`DS4_PROMPTCACHE_INCONCLUSIVE.md` — *"with `-ncmoe 40`, expert weights stream from CPU memory
on every token, so the second arm inherited a warm page cache"* — and it still nearly produced
a false regression claim on a different test. Naming a confound once does not inoculate the
next measurement against it.

## RESOLVED 2026-08-02 — controlled A/B: no regression

Two A/B attempts. The first was **void**; the second answers it.

**Attempt 1 (void).** Design: K=4/arm, discard draw 1 as cold, order new → old → new.

| arm | warm mean | spread |
|---|---|---|
| new_a | 4.65 | 2.4 % |
| old | 4.25 | 32.7 % |
| new_b | 4.16 | 42.3 % |

Pre-registered rule — *void if |new_a − new_b| ≥ |old − new_\*|* — fired hard:
|new_a − new_b| = **0.49** vs 0.40 and 0.09. **The same binary differed from itself more than
from the other binary.** Cause: "discard draw 1" assumed warming finishes in one generation.
It does not — `old` ran 3.41 → 4.55 → 4.80 and `new_b` 3.05 → 4.61 → 4.81 *across the draws
being averaged*. Whichever arm warmed fastest won on an artifact.

**Attempt 2.** Fix: stop guessing where warm begins — **4 explicit pre-warm draws discarded**,
then 4 measured; any arm spreading >8 % reported UNSTABLE rather than averaged.

| arm | pre-warm (discarded) | measured | mean | spread |
|---|---|---|---|---|
| new_a (10260) | 1.57, 3.76, 4.71, 4.74 | 4.72, 4.71, 4.71, 4.72 | **4.71** | **0.2 %** |
| old (10245) | 1.83, 3.23, 4.59, 4.76 | 4.71, 4.71, 4.76, 4.73 | **4.73** | **1.1 %** |
| new_b (10260) | 2.07, 3.96, 4.79, 4.78 | 4.72, 4.74, 4.74, 4.76 | **4.74** | **0.8 %** |

**Conclusion: no detectable decode difference between `42974d12` and `331981025`.** All three
arms fall within 0.03 t/s (0.6 %). The suspected 17 % regression from
`4330be608 cuda: sum MoE expert outputs on decode` does not exist; the original signal was
entirely cold-cache artifact.

### The pre-registered rule is under-specified, and it matters

By the letter, attempt 2 also voids: |new_a − new_b| = 0.03 ≥ |old − new_a| = 0.02.

Applying that mechanically would be wrong. The rule was written to catch *noise swamping
signal*, and tacitly assumed the differences would be large enough to argue about. Here every
difference sits at the resolution floor — within-arm spread ≤1.1 %, across-arm range 0.6 % —
while the effect under investigation was **17 %, roughly 27× larger than anything observed**.
A rule that voids a result *because the arms agree too well* is a specification error.

**Better formulation for future use:** void if
`|new_a − new_b| ≥ max(|old − new_*|)` **AND** `max spread across arms ≥ (effect size of
interest) / 3`. That is, require the instrument to be *incapable* of resolving the effect,
not merely to rank the arms in an inconvenient order. Recorded because pre-registration is
only protective if the rule is written to be interpretable at both ends of the scale.

### A real difference that is not throughput

gzip is **0.4545 on `42974d12`** and **0.4743 on `331981025`**, constant across all four
measured draws within each build. The Laguna merge changed DS4's *output* while leaving decode
rate untouched — expected, since `4330be608` alters MoE summation order and therefore
floating-point results. Both values sit in the healthy band, and each build is internally
deterministic. **This is a numerical change, not a quality claim in either direction** — gzip
detects degeneration, not fidelity, and no reference exists to measure DS4 fidelity against on
this fleet (BF16 is ~570 GB).

## Limits

- One configuration, one prompt, 200 tokens, one machine. The 2.7× warm-up ratio is specific
  to `-ncmoe 40` on this box's RAM and disk.
- Three draws in one process. Where the curve plateaus is unknown — draw 3 was still rising
  (4.21 → 4.75), so the true warm ceiling may be above 4.75 t/s.
- No A/B against `42974d12` was run. The claim here is "no evidence of regression," not
  "regression excluded" — the historical figures are cold and today's warm figures exceed
  them, so any real regression would have to be smaller than the warm-up effect hides.
- Page-cache state is not controlled or reported by any prior DS4 receipt on this fleet.

## Provenance

- `.194:~/ds4_decode_k3/` — `k3.log`, `server.log`, `resp_d{1,2,3}.json`
- Script `~/ds4_decode_k3.sh`; local copy `scratchpad/ds4_decode_k3.sh` (**contains the
  interleaving parser bug** — read the raw `eval time` lines, not its per-draw output)
- Historical logs: `~/ds4_ts/server_n40_ts_bal.log`, `~/ds4_sweep/server_ncmoe40.log`,
  `~/ds4_probe/`
