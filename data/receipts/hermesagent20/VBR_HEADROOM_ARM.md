# VBR headroom arm — budget mis-sizing, retraction, and rerun

Node `.73` (2× Tesla P100, sm_60, 1063 MHz / 150 W). Build `a8e5b5a38` (buun VBR fork).
Model `Hermes3.6-35B-A3B-Uncensored-Genesis-V5-APEX.gguf`. Dataset wikitext-2-raw.
Date 2026-07-28.

## The question (buun, verbatim)

> "With turbo4 you can fit, lets say, 150k context window max. Then with VBR you do
> `-ct vbr --vbr-floor t4`. What is the KLD at ~80k tokens, or 100k tokens? Because strictly
> speaking, the vbr KLD will not be as bad as turbo4 until the very limit of turbo4's max
> context window."

Static turbo4 pays 4-bit cost at token 1. You size it for worst-case context and then spend
most of your time far below that. VBR holds f16 until pressure forces it down, so it should
beat turbo4 at every fill level except the maximum. Host RAM caps KLD at ctx 32768 here
(logits buffer = ctx × vocab × 4 B), so 32768 stands in for buun's 150k.

## RETRACTED: arm 1 (budget 644 MiB) is invalid

Results below are **not** a test of the prediction and must not be cited.

```
ctx    chunks  fill_pct  status  median_kld  same_top  ppl_q     secs
2048   32      6.2       OK      0.000000    100.000   6.031433  316
8192   12      25.0      OK      0.000000    99.974    5.854095  489
16384  6       50.0      OK      0.000000    100.000   5.052809  534
32768  3       100.0     OK      0.000000    99.951    6.444426  862
```

**Why it is invalid.** The budget was set to 644 MiB, derived from a VBR run's pool
reservation under a t4-priced fit (`VBR pool #0: 324.00 MiB` + `#1: 320.00 MiB`). That
reservation is sized at VBR's **f16 entry tier** — where it starts — not at the floor tier's
cost. Measured directly instead (`alloc_probe/`, init-only, ctx 32768, 10 KV layers,
1/1 seqs):

| codec | total KV | K | V |
|---|---|---|---|
| f16 | **640.00 MiB** | 320.00 | 320.00 |
| turbo8 | 325.00 MiB | 162.50 | 162.50 |
| turbo4 | **165.00 MiB** | 82.50 | 82.50 |

644 MiB exceeds f16's entire footprint (640 MiB). VBR was never under pressure and could
have run at f16 throughout — which is what it did. The arm measured **unconstrained VBR**
against static turbo4, so "VBR beats turbo4 at 100 % fill" is an artifact of handing VBR
3.9× turbo4's memory.

Corroborating log evidence from `logs/vbr_hr_ctx32768.log`:

- `vbr_floor_clamp_order: VBR floor 4.125 bits/value: degrade order clamped at 40/100 steps`
  — with a t4 floor, at most 40 of the 100 baked steps are reachable.
- Only **11** steps were used. 33 total degrade events = 11 steps × 3 chunks.
- All degrades fire between 30720 and 32768 cells — the last ~2048 tokens of each chunk:
  `VBR degrade #11: cache_v_l19 L19 -> turbo8 (30720 cells transcoding on side stream)`.
  Every degrade lands on `-> turbo8`; the t4 floor is never approached.
- Final projections `310.00 / budget 324.00` (device 0) and `300.00 → 180.00 / budget 320.00`
  (device 1). The trigger was the **per-device split** (f16 needs exactly 320 MiB/device
  against a 320 MiB device budget), not the aggregate.

So even the 11 steps are a rounding artifact of the split, not genuine budget pressure.

### Second defect: the p999 column was garbage

`num()` took the first float on the matched line. For `99.9%   KLD:   0.302965` that is the
**label**, so every row read `99.9`. Column dropped from the retracted table above; fixed in
arm 2 by taking the text after the last colon.

### Third item, reported not interpreted

Degrades *did* fire during a prefill-only instrument (`transcoding on side stream`). buun's
standing position is that the dynamic degrade path is decode-only and prefill sets structure
up front. These log lines are recorded verbatim for him to adjudicate; they are not claimed
here as evidence that the decode path was exercised, nor flattened into "best case only."

## Arm 2 (budget 165 MiB) — the matched test

Budget = **turbo4's measured cost at the context ceiling** = 165 MiB, floor t4. This is
buun's design: size for turbo4 at max context, then ask what VBR delivers below the ceiling.

f16 demand vs the fixed 165 MiB budget:

| ctx | fill of ceiling | f16 demand | vs budget | predicted |
|---|---|---|---|---|
| 2048 | 6.2 % | 40 MiB | fits | f16 quality |
| 8192 | 25 % | 160 MiB | just fits | f16 quality |
| 16384 | 50 % | 320 MiB | ~2× over | partial degrade, ~turbo8 region |
| 32768 | 100 % | 640 MiB | ~4× over | forced to t4 aggregate → converges to turbo4 |

That is buun's prediction as a falsifiable ladder. Comparison targets are the static cells
already in the panel:

| ctx | turbo4 same_top | turbo4 median KLD | f16 same_top |
|---|---|---|---|
| 2048 | 96.786 | 0.002363 | 100.000 |
| 8192 | 96.970 | 0.001941 | 99.992 |
| 16384 | 96.732 | 0.001938 | 100.000 |
| 32768 | 96.665 | 0.002166 | 99.994 |

**Falsification condition:** if the ctx 32768 cell does not land near turbo4's 96.665 /
0.002166, either the prediction's convergence clause is wrong or the budget is still
mis-sized. Given arm 1, budget sizing is checked first.

### Arm 2 results (complete, 2026-07-28 12:20–12:59)

```
ctx    chunks fill%  mean_kld   median_kld  p999_kld  same_top  ppl_q     degrades max_step secs
2048   32     6.2    0.000001   0.000000    0.000237  99.997    6.031444  0        0        319
8192   12     25.0  -0.000000  -0.000000    0.000050  99.992    5.854192  0        0        483
16384  6      50.0   0.002595   0.000567    0.091333  97.984    5.054659  210      35       570
32768  3      100.0  0.006430   0.002148    0.245975  96.700    6.457115  120      40       932
```

**Convergence at the ceiling — confirmed.** ctx 32768 VBR vs static turbo4:

| metric | VBR @165 MiB | static turbo4 | Δ |
|---|---|---|---|
| same_top | 96.700 | 96.665 | +0.035 pt |
| median KLD | 0.002148 | 0.002166 | −0.8 % |
| mean KLD | 0.006430 | 0.006164 | +4.3 % |
| p99.9 KLD | 0.245975 | 0.228859 | +7.5 % |
| PPL(Q) | 6.457115 | 6.456460 | +0.01 % |

Mechanism confirms the outcome rather than merely agreeing with it: `max_step 40` is exactly
the `vbr_floor_clamp_order` limit, and tier targets are `60 -> turbo8, 60 -> turbo4` =
20 tensors × 3 chunks taken to turbo8 and then all 20 on to turbo4. VBR exhausted the ladder
and ended at uniform turbo4. It arrives there progressively rather than starting there,
which is why it is a hair better, not identical.

**The prediction's two clauses both hold: VBR beats turbo4 below the ceiling, and converges
to it at the ceiling.**

### CAVEAT that qualifies the headline: at 50 % fill, a static codec wins

KV size is exactly linear in cells, so from the measured ctx-32768 footprints the best
*static* codec that fits the same 165 MiB budget at each depth is:

| ctx | f16 | turbo8 | turbo4 | best static that fits | its same_top | VBR same_top |
|---|---|---|---|---|---|---|
| 2048 | 40 | 20.3 | 10.3 | f16 | 100.000 | 99.997 |
| 8192 | 160 | 81.3 | 41.3 | f16 | 99.992 | 99.992 |
| 16384 | 320 ✗ | **162.5** | 82.5 | **turbo8** | **98.637** | **97.984** |
| 32768 | 640 ✗ | 325 ✗ | 165 | turbo4 | 96.665 | 96.700 |

(MiB; ✗ = exceeds budget. The turbo8 and turbo4 figures at ctx 16384 are **measured**, not
extrapolated — `alloc_probe/alloc_turbo8_16384.log`, `alloc_turbo4_16384.log`. Sub-ceiling
figures at 2048/8192 remain computed from the measured 32768 values.)

So VBR matches the best static option at 3 of 4 depths and **loses by 0.65 pt at 16384**,
where uniform turbo8 fits the budget and VBR does not reach it.

**turbo8 fits, but barely — and the margin is the story.** Measured per device at ctx 16384
against VBR's per-device budget split:

| device | static turbo8 needs | VBR budget | margin |
|---|---|---|---|
| 0 | 81.38 MiB | 83.52 MiB | 2.14 MiB |
| 1 | 81.25 MiB | 81.48 MiB | **0.23 MiB** |

VBR allocates a 1.25 MiB/device f16 sink-stash (`vbr_stash_ensure`) and maps in 2 MiB VMM
pages. Either one alone exceeds device 1's 0.23 MiB margin. So VBR structurally cannot hold
uniform turbo8 at this depth even though a static allocation can — the dynamic machinery's
own overhead is larger than the headroom.

**It then over-degrades past that point.** Observed, not inferred:

- Final tier composition at 16384: `120 -> turbo8, 90 -> turbo4` over 6 chunks = per chunk
  all 20 tensors to turbo8, then 15 of them on to turbo4. End state **15×turbo4 + 5×turbo8**.
- Device 0 ends at `projected 80.00 / budget 83.52` — *below* the 81.38 that uniform turbo8
  would need, despite having 3.5 MiB of unused budget. So device 0 was degraded further than
  its own budget required.

**Unreconciled accounting.** Two figures for the same end state disagree and only the
composition is safe to cite:

- Tier arithmetic on the final composition: 15 × 4.125 + 5 × 8.125 = **102.5 MiB**.
- The controller's own final projections: 80.00 + 64.00 = **144.00 MiB** of 165.00.

The last projection is timestamped 19 µs after the final degrade, and the degrade lines say
`mapped … pre-release`, so the 144 figure plausibly includes buffers not yet released. That
is a hypothesis I have not sized. **The robust claim is the tier composition** (VBR ended
below uniform turbo8 while turbo8 was affordable); the "38 % of budget unspent" reading has
been withdrawn as unsupported.

**Open question for buun rather than a recommendation:** device 0 degraded below what its
own budget allowed while device 1 was the binding constraint. Does the degrade order account
for device affinity? The degrade lines do carry `device 0` / `device 1` tags, so the
controller is not device-blind — but the end state looks like pressure on the tighter device
pulling down tensors on the looser one. If that reading is right, a per-device-aware order
may recover part of the 0.65 pt. Stated as a question because the ordering logic has not
been read.

This is an efficiency limitation of the controller in the multi-GPU case, not a defect in
the dynamic-KV concept — at the ceiling (32768) it uses the full budget and converges
correctly.

### Arm 1's diagnosis, confirmed by arm 2's own log

Arm 2 at ctx 32768 prints `VBR pool #0 (device 0): 324.00 MiB buffer, 324.00 MiB used` and
`pool #1: 320.00 MiB` — the same 324/320 reservation as arm 1 — while its *budget* lines
read `83.01 / 81.99 MiB`. Reservation is sized at the f16 entry tier; the budget is the
actual constraint. That is precisely the conflation that made arm 1 invalid, now visible
side by side in a single run.

## Labelling note

The main panel's `vbr` rows and this arm's `vbr` rows are **different experiments** and must
not share a row label. Panel `vbr` ran
`KV budget auto (remaining VRAM, resolved by fit), entry tier f16, floor 1.25 bits/value`
— unconstrained, default floor. This arm is floor t4 at a fixed budget.

## Standing caveat (buun) — applies to the whole KLD panel

`llama-perplexity` is teacher-forced: **all prefill, no decode.** On prefill VBR knows the
final cost up front and sets KV structure immediately rather than degrading as tokens
arrive. The genuine on-the-fly degrade happens during DECODE, which this instrument never
exercises. Every number in the panel and in this arm is VBR's best case.

## Provenance

- Retracted arm: `.73:/home/mark/kv-panel/vbr_headroom/` (script `vbr_headroom_arm.sh`)
- Allocation probe: `.73:/home/mark/kv-panel/alloc_probe/` (script `measure_kv_alloc.sh`)
- Arm 2: `.73:/home/mark/kv-panel/vbr_headroom_165/` (script `vbr_headroom_arm2.sh`)
- Panel: `.73:/home/mark/kv-panel/run/logs/`, results in `kv_kld_results.tsv`
