# KV-codec KLD panel — Genesis V5 (MoE), `.73`

**Started 2026-07-27.** `.73`, dual Tesla P100 (sm_60), 1063 MHz / 150 W.
Model `Hermes3.6-35B-A3B-Uncensored-Genesis-V5-APEX` (weights constant across all cells —
only `-ctk`/`-ctv` vary). Binary `buun_vbr/build/bin/llama-perplexity`.
Dataset wikitext-2 test. `-fa on`, `-ngl 99`, matched between bases and cells.

**Why KLD and not an agent benchmark.** The original plan was to compare KV codecs by agent
pass rates. buun predicted *"the test saturates on every kv type"* and he was right —
HermesAgent-20 has ~6 usable signal points, and this session proved its scores are a lossy
hash of the output (`DETERMINISM_ROOT_CAUSE.md`). KLD is continuous, teacher-forced,
thousands of per-token comparisons per cell, no sampler, no agent loop, no wall-clock ceiling.

**Reading rule, fixed before results.** Mean KLD alone **misranks mixed-precision schemes** —
it treats all divergence as loss, so a codec that *reallocates* precision can look worse while
preserving what matters. `same_top_p` and RMS Δp are reported alongside and carry equal weight.

**Calibration anchor.** The sm_60 FAST_FP16 defect measured **median KLD 0.0023 /
same-top 96.5 %** and was behaviourally visible enough that two forks merged a fix. Cells are
read against that, not against zero.

## Instrument gate — PASSED

`f16` vs the `f16` base must be ~0. It is:

| tier | mean KLD | median KLD | same-top | PPL |
|---|---|---|---|---|
| 2048 | −0.000000 | 0.000000 | **100.000 %** | 6.0314 |
| 8192 | −0.000000 | −0.000000 | **99.992 %** | 5.8542 |
| 16384 | 0.000000 | 0.000000 | **100.000 %** | 5.0528 |

**Noise floor: same-top 99.992 % at 8192** — ~8 tokens of 98,304 flipped between two runs
that should be bit-identical. That is the same nondeterminism class documented elsewhere in
these receipts, appearing in the measurement path itself (`-fa` reduction order the likely
cause). It is **~400× smaller than the calibration defect**, so there is ample headroom, but
a codec reading "same-top 99.99 %" is **at the floor**, not perfect.

**PPL falls monotonically with depth** (6.03 → 5.85 → 5.05), confirming the tiers genuinely
deepen context rather than silently truncating.

## Depth ladder — and the constraint that shaped it

The KLD logits buffer is **ctx × vocab × 4 B**, held in **host RAM**:

| tier | buffer | `.73` (15 GB RAM) |
|---|---|---|
| 2048 | 1.2 GB | base built, 16 GB on disk |
| 8192 | 5.0 GB | base built, 23 GB |
| 16384 | 10.0 GB | base built, 23 GB — **carried by 16 GB Optane swap** |
| 32768 | 19.9 GB | **OOM-killed** (`dmesg`: anon-rss 12.1 GB, global_oom) |

**Long-context KLD profiling is host-RAM-bound, not VRAM-bound.** This is not obvious and it
determines how deep any KV study can go. `.194` (60 GB RAM) can reach 32768 natively; 128 GB
would reach 65536.

## Results — 21/21 cells, all OK

| type | tier | mean KLD | median KLD | p99.9 KLD | same-top % | PPL(Q) |
|---|---|---|---|---|---|---|
| f16 | 2048 | -0.000000 | 0.000000 | 0.000051 | 100.000 | 6.031433 |
| f16 | 8192 | -0.000000 | -0.000000 | 0.000050 | 99.992 | 5.854192 |
| f16 | 16384 | 0.000000 | 0.000000 | 0.000051 | 100.000 | 5.052809 |
| vbr | 2048 | -0.000000 | 0.000000 | 0.000051 | 100.000 | 6.031433 |
| vbr | 8192 | 0.000008 | 0.000000 | 0.001659 | 99.988 | 5.854228 |
| vbr | 16384 | 0.000000 | 0.000000 | 0.000051 | 100.000 | 5.052809 |
| q8_0 | 2048 | 0.001531 | 0.000341 | 0.080004 | 98.674 | 6.030953 |
| q8_0 | 8192 | 0.001098 | 0.000245 | 0.054109 | 98.757 | 5.857284 |
| q8_0 | 16384 | 0.001278 | 0.000239 | 0.069881 | 98.677 | 5.055155 |
| turbo8 | 2048 | 0.001767 | 0.000395 | 0.087316 | 98.528 | 6.029722 |
| turbo8 | 8192 | 0.001255 | 0.000280 | 0.058316 | 98.708 | 5.854723 |
| turbo8 | 16384 | 0.001321 | 0.000273 | 0.064899 | 98.637 | 5.052871 |
| turbo4 | 2048 | 0.007365 | **0.002363** | 0.302965 | **96.786** | 6.035988 |
| turbo4 | 8192 | 0.005448 | 0.001941 | 0.191882 | 96.970 | 5.860298 |
| turbo4 | 16384 | 0.006572 | 0.001938 | 0.224115 | 96.732 | 5.055774 |
| turbo3 | 2048 | 0.015922 | 0.005694 | 0.649648 | 94.914 | 6.069293 |
| turbo3 | 8192 | 0.012694 | 0.004759 | 0.414119 | 95.189 | 5.888928 |
| turbo3 | 16384 | 0.014569 | 0.004766 | 0.531605 | 95.056 | 5.078656 |
| turbo2 | 2048 | 0.042513 | 0.016453 | 1.243717 | 91.386 | 6.208053 |
| turbo2 | 8192 | 0.038317 | 0.015009 | 1.236571 | 92.059 | 5.989540 |
| turbo2 | 16384 | 0.042525 | 0.014884 | 1.525624 | 91.743 | 5.170346 |

### 0. The anti-substitution guard FAILED — validated by other means

`meta.txt` records:

```
bpw@ctx2048: f16=16.000 q8_0=16.000! turbo8=16.000! turbo4=16.000! turbo3=16.000!
             turbo2=16.000! vbr=16.000!
```

The effective-BPW probe — the guard specifically included to catch silent K/V type
substitution — **reports 16.000 for every type**, including turbo2, which is impossible.
It measured nothing. **Do not cite these BPW numbers, and do not rely on that guard on this
build.**

The cells are still valid, established independently:

1. **Per-cell logs show codec-specific initialisation.** turbo2: `TURBO meansub (device 0):
   K-mean BAKED table (10 live layers)`. turbo8: TCQ codebooks loaded. vbr: `VBR dynamic
   runtime controller ... entry tier f16, floor 1.25 bits/value ... decode-time degrade
   controller armed`, `KV VRAM budget 5121 MiB`.
2. **The KLD ladder is monotone in bitrate** (q8_0 < turbo8 < turbo4 < turbo3 < turbo2). Under
   a silent fallback to f16 every row would read ~0 like f16 does. They do not.

**The row where this mattered most is `vbr`**, since "vbr == f16" is exactly what a silent
fallback would produce. The log resolves it: the VBR controller was armed with a 5121 MiB
budget and a 1.25 bits/value floor, and simply never degraded — at these context depths the
cache never approached the budget. So **VBR was active and chose to stay at f16**, which is the
intended behaviour, not an inert flag.

(Note the floor here is **1.25 bpv**, the default — the serving config uses
`--vbr-floor 6.125`. Not a factor since no degradation occurred, but the two are not the same
configuration.)

### 1. turbo4 costs almost exactly what the sm_60 bug cost

| | median KLD | same-top |
|---|---|---|
| sm_60 FAST_FP16 defect (anchor) | 0.0023 | 96.5 % |
| **turbo4 @ 2048** | **0.002363** | **96.786 %** |

A defect that two forks merged a fix for, reproduced as a deliberate design point. This is the
line the ladder needed: **turbo8 sits ~6× below it, turbo3 ~2.5× above, turbo2 ~7× above.**

Practical read: turbo8 is comfortably safe; turbo4 is where you begin paying a known-bad
amount of fidelity; turbo3 and below are visibly degraded and should be a deliberate choice.

### 2. VBR at entry tier is indistinguishable from f16

median 0.000000 and same-top 100.000 / 99.988 / 100.000 — identical to f16's own readings
(f16 itself read 99.992 at 8192, the instrument floor). PPL matches f16 to 4 decimal places
at 2048 and 16384.

**Scope limit, stated plainly: VBR never degraded during these runs.** `llama-perplexity`
applied no VRAM pressure, so this confirms *the entry tier is lossless* and says **nothing**
about VBR's degraded tiers. Measuring those needs a run under real budget pressure.

### 3. turbo8 ≈ q8_0 — the difference is throughput, not fidelity

median 0.000395 vs 0.000341; same-top 98.528 % vs 98.674 %. q8_0 is marginally ahead on both,
turbo8 marginally ahead on PPL. **They are the same fidelity tier.** This settles the objection
buun raised about conflating them: the conflation was wrong as an argument, but the two
genuinely are equivalent in fidelity — so the choice between them is a speed/VRAM decision.
(Serving throughput measured earlier: f16 prefill 127–148 t/s vs q8_0 78–82 t/s.)

### 4-REVISED (2026-07-28, after adding ctx=32768) — the depth trend was over-read

**The section below was written on three depth points and is RETRACTED as a trend claim.**
The original text is kept beneath this revision because the mistake is the useful part.

A fourth tier (32768×3, run on `.73` after adding a 32 GB NVMe swapfile — 48 GB total swap,
peak 24 GB in use) changes the picture in two ways.

**First, a confound that invalidates cross-tier trend reading.** `PPL(Q)` for f16 across the
four tiers:

```
2048: 6.031433    8192: 5.854192    16384: 5.052809    32768: 6.444489
```

**Not monotone.** PPL fell with depth and then jumped 27 % at 32768. Since the model and
dataset are fixed, the only thing that changed is *which tokens get scored with how much
context* — `llama-perplexity` chunks differently per `-c`, so each tier scores a different
token population. **Cross-tier comparisons are therefore comparing different populations, and
any "damage grows/shrinks with depth" claim from this design is confounded.**

**Second, what the data actually shows once you stop reading a trend into it: the codec
damage is approximately depth-invariant.**

| type | same-top % @ 2048 / 8192 / 16384 / 32768 | spread |
|---|---|---|
| q8_0 | 98.674 / 98.757 / 98.677 / 98.743 | **0.1 pts** |
| turbo8 | 98.528 / 98.708 / 98.637 / 98.659 | **0.2 pts** |
| turbo4 | 96.786 / 96.970 / 96.732 / 96.665 | **0.3 pts** |
| turbo3 | 94.914 / 95.189 / 95.056 / 95.025 | **0.3 pts** |
| turbo2 | 91.386 / 92.059 / 91.743 / 91.086 | **1.0 pts** |

Across a **16× context range** — and despite the token-population confound — `same_top` moves
by at most 1 point, and under 0.3 points for everything at turbo4 and above. Median KLD wobbles
15–45 % with no consistent direction; p99.9 wobbles 23–58 % with no consistent direction and
was the statistic that produced the false trend.

**The honest conclusion: over 2048–32768, KV-quantisation damage is roughly constant with
depth.** It does not grow, and it does not shrink. The earlier "median falls, tail rises"
reading was noise in a three-point series, amplified by p99.9 being the least stable number in
the table.

**Consequence for VBR, and it is the reassuring one.** The concern was: if damage worsens at
long context, VBR degrading under pressure fails exactly when context is full and fidelity
matters most. **The data does not support that failure mode.** Damage at 32768 is
indistinguishable from damage at 2048 for every codec. Degrading at depth costs what degrading
anywhere costs.

That is weaker than the flattering story ("damage is *lower* at depth, so VBR is optimal") and
stronger than the feared one ("damage is *higher* at depth, so VBR fails under pressure").
**Neither holds. It is flat.**

**Still unmeasured, and still the question that matters:** VBR never degraded in any of these
28 cells. Whether *price-ordered per-layer* degradation beats *uniform* quantisation at equal
aggregate bitrate is untested. `--vbr-vram-budget SIZE` and `--vbr-floor {f16,t8,t4,t3,t2,t1}`
exist and make it directly testable: force VBR to a ~4 bpv aggregate and compare against static
turbo4 at matched depth.

---

*Original three-point section, retained:*

### 4. The depth trend splits — median falls, tail rises

Consistent across **every** codec:

| turbo2 | 2048 | 8192 | 16384 |
|---|---|---|---|
| median | 0.016453 | 0.015009 | **0.014884** ↓ |
| p99.9 | 1.243717 | 1.236571 | **1.525624** ↑ |

Median KLD falls from 2048 → 8192 and plateaus; the p99.9 tail falls then **climbs again at
16384**, exceeding its 8192 value for every codec. Deeper context makes the typical token more
robust (PPL falls 6.03 → 5.85 → 5.05, the model is more confident) while the worst tokens get
worse. **KV damage becomes rarer and more severe with depth, not uniformly smaller.**

**This falsifies the rationale originally given for building the depth ladder** — "KV error
scales with cached-token count, which is why shallow benchmarks show nothing." Wrong for the
median, right for the tail.

It also means the flattering reading for VBR — *"quantization is most damaging at short
context, so degrading only at depth is optimal"* — is **only half supported**. True of the
median, false of the tail. VBR's policy trades typical-case safety for tail risk. Still
defensible, but a different claim.

Caveat: three depth points, one model, one dataset. The tail is by construction the noisiest
statistic here.

### 5. Tail-vs-median ratio confirms damage is concentrated

q8_0 @ 2048: median 0.000341, p99.9 0.080004 — a **235×** ratio. Every codec shows the same
shape. KV quantization does not uniformly blur the distribution; it leaves most tokens nearly
untouched and occasionally flips one hard.

This is the quantitative form of the objection that mean KLD misranks mixed-precision schemes:
a codec that concentrates error where it does not matter can post a worse mean and a better
`same_top`. Report both, always.

## Harness failures encountered building this

Recorded because each produced a plausible-looking state rather than an error:

1. **`export KV_TIERS=` without `${VAR:-default}`** silently clobbered a smoke-test override,
   so a 4-chunk validation ran as the full ladder.
2. **`timeout 1800` killed the wrapper but not the child `llama-perplexity`.** The orphan kept
   running and holding VRAM.
3. **A relaunch deleted the file that orphan was still writing.** The computation completed
   (`Final estimate: PPL = 5.8542`) into an unlinked inode — data unrecoverable — and the new
   attempt OOMed on VRAM the orphan still held.
4. **`pgrep -x llama-perplexity` never matches.** The name is 16 chars; `comm` truncates at 15.
   The wait loop silently reported "not running" and fell straight through.
5. **`[ -s "$out" ]` as a completion check.** A base killed partway leaves a large, valid-looking
   file; reusing it would have compared against truncated logits and produced wrong numbers
   with no error.

Fixes now in the scripts: completion gated on `Final estimate: PPL` in the tool's own log;
the whole panel is one sequential process with a guard that refuses to start if any llama
process holds the GPUs; a tier that fails drops itself rather than aborting the panel; the
tier list derives from `KV_TIERS` as single source of truth.

Apparatus on `.73`: `~/kv-panel/{kv_panel_env.sh,gen_bases.sh,run_panel.sh,kv_kld_sweep.sh}`.
