# Result -- P-L0 gate: PASS. The EXL3 campaign's reference reproduces exactly.

**2026-09-19, 10:48:01 to 11:05:22 EDT (17 min 21 s), node `.73`** (`ai-p100-sli`, dual Tesla
P100, sm_60). Prereg: `PREREG_CODEC_LADDER.md`, committed before any cell ran.

P-L0: *"Re-running the reference against itself gives mean KLD < 1e-4 and same-top >= 99.9%.
Without this the ladder is not reproducible and nothing below counts."*

## Verdict

| gate | required | measured | |
|---|---|---|---|
| mean KLD | < 1e-4 | **0.000000 +/- 0.000000** | PASS |
| same top p | >= 99.9% | **100.000 +/- 0.000 %** | PASS |

**P-L0 CONFIRMED.** The ladder is cleared to proceed.

## Why this run existed

**CORRECTION, 2026-09-19 12:45.** This section originally claimed the reference *"had never been
checked against itself"* and that *"a grep of `data/receipts/exl3-campaign/` finds no self-check."*
**Both statements are false.** `RESULT_EXL3_KLD.md` carries the row `R2 Q8_0, the gate` with
exactly this measurement. My grep searched for the phrases "self-check" / "reference against
itself", which do not appear there -- the row is labelled "the gate". Searching for words instead
of for the measurement, then asserting a negative from the miss, is the error.

What this run actually is, and it is worth more than the claim it replaces: **an independent
reproduction of that gate, weeks later, to every printed digit.**

| | mean KLD | median | 99% KLD | same-top | PPL(Q) |
|---|---|---|---|---|---|
| EXL3 campaign, `R2` | 0.000000 +/- 0.000000 | -0.000000 | 0.000038 | 100.000 +/- 0.000 | 5.9325 |
| **P-L0, today** | 0.000000 +/- 0.000000 | -0.000000 | 0.000038 | 100.000 +/- 0.000 | 5.932464 |

Same binary, same flags, same corpus, same reference, different day, different process, same
numbers -- including the 99th-percentile tail at `0.000038`, which is the digit most likely to
move if anything had drifted. `ref.kld` is reproducible, and now demonstrably so across sessions
rather than within one.

The gate also ran **first by design**, ahead of the five stock cells. A gate that runs last can
void five cells after they have been paid for; the prereg's own language is that nothing below it
counts.

## Full statistics

```
====== Perplexity statistics ======
Mean PPL(Q)                   :   5.932464 +/-   0.140928
Mean PPL(base)                :   5.929072 +/-   0.140628
Cor(ln(PPL(Q)), ln(PPL(base))):  99.99%
Mean ln(PPL(Q)/PPL(base))     :   0.000572 +/-   0.000351

====== KL divergence statistics ======
Mean    KLD:   0.000000 +/-   0.000000
Maximum KLD:   0.000053      Minimum KLD:  -0.000059
99.9%   KLD:   0.000050       0.1%   KLD:  -0.000053
99.0%   KLD:   0.000038       1.0%   KLD:  -0.000037
Median  KLD:  -0.000000

====== Token probability statistics ======
RMS Dp    :  0.001 +/- 0.000 %      Maximum Dp: 0.006%   Minimum Dp: -0.005%
Same top p: 100.000 +/- 0.000 %
```

Same top p was **100.000% on every one of the 40 chunks individually**, not merely in aggregate.
Checked by scanning all 40 chunk rows in `logs/gate_pl0_run.log` for any row not reading
`100.000`, rather than by eyeballing the dozen chunks that happened to appear in progress polls.

## The number that is not zero, stated rather than buried

`Mean ln(PPL(Q)/PPL(base)) = 0.000572 +/- 0.000351`, i.e. perplexity reads **0.057% high**, at
**1.63 sigma**. Not significant, and it shrank monotonically as chunks accumulated (0.00121 at
chunk 5, 0.00030 by chunk 35), which is what a noisy estimator converging on zero looks like.

Recording it because it is the one figure that is not identically zero, and "the reference
reproduces bit-exactly" would be a stronger claim than the data supports. The honest statement is
that the **distributions** are identical to the limit of measurement (KLD zero, same-top 100%,
RMS Dp 0.001%) while the **perplexity ratio** carries sub-sigma noise.

## What the floor actually is -- this matters for P-L5

The mean KLD's own uncertainty printed as `0.000000`, so the **mean** is reproducible to better
than 1e-6. The *per-token* distribution is wider: individual tokens span **-5.9e-5 to +5.3e-5**,
symmetric about zero, which is numerical noise in the estimator rather than a real divergence.

**P-L5 is scored on mean KLD**, and its preregistered threshold is 1e-4. Against a mean-KLD floor
below 1e-6, that threshold is roughly **100x looser than the instrument**. So P-L5 is a genuine
discriminator and, if anything, a conservative one: two containers of the same ternary weights
that differ by more than 1e-4 in mean KLD cannot blame the instrument.

That was not guaranteed going in. Had the floor come back at 3e-5, P-L5's 1e-4 threshold would
have been mostly noise and the control would have been close to worthless.

**One limit on how precisely the floor can be known.** `llama-perplexity` prints mean KLD to six
decimals, so this run establishes the floor as **< 5e-7** and no better; the true value could be
anything below that. Every cell's mean KLD is printed at the same resolution, which means
differences between cells cannot be resolved below ~1e-6 whatever the underlying instrument can do.

The practical consequence: **the agreement tests (P-L5 and C-XBIN) must be scored against the
preregistered 1e-4, not against "the measured floor".** A threshold at or below 1e-6 would convert
last-digit rounding into a verdict -- it would report an implementation defect, or a confounded
panel, on the strength of a rounding step. `tools/score_ladder.py` defaults to 1e-4 and warns if a
lower threshold is passed.

## Provenance, verified by hash

| item | identity | check |
|---|---|---|
| model | `Qwen3.8-27B-Q8_0.gguf`, 29,047,086,048 B | sha256 `a680f44a06920e5d689774823782006aa3acc8db95750323373b24139b67e348`, **verified on both ends** |
| reference | `/mnt/HDD/kld/ref.kld`, 5,065,891,540 B | original from the EXL3 campaign |
| corpus | `/mnt/HDD/exl3/wiki.test.raw` | sha256 `173c87a5...`, matches the campaign |
| binary | `buun-sm60-qual` `9ae8f0f4` + e8m0 guard | the build that wrote `ref.kld` |
| host | `.73`, dual P100, 32 GB VRAM total | the hardware that wrote `ref.kld` |

**A transfer-verification defect was caught here.** The gate model's transfer log recorded a
single sha256 and reported success. That hash turned out to be the **source**; the remote copy had
never been hashed. Both ends were then hashed independently and matched. The prereg's own warning
applies directly -- twelve files named `wiki.test.raw` on this machine are 14-byte HTTP 404 bodies
-- and a one-sided hash is not a verification, it is a receipt for a file you already had.

## Frozen invocation

```
llama-perplexity -m /mnt/HDD/ladder/Qwen3.8-27B-Q8_0.gguf -f /mnt/HDD/exl3/wiki.test.raw \
  -ngl 99 -sm layer -c 512 -b 512 -ub 8 --chunks 40 -fa on -ctk f16 -ctv f16 \
  --kl-divergence-base /mnt/HDD/kld/ref.kld --kl-divergence
```

Identical to `exl3_kld_arm.py`. Not one flag varied. The binary reported
`CUDA : ARCHS = 600 | USE_GRAPHS = 1 | TURBO_FA = 1`, 6 threads, 40 chunks at n_ctx 512.

`llama-perplexity` exits 0 on failure, so the verdict above is parsed from the KLD block. `RC=0`
was recorded but carries no information.

## Operational notes

**The node's VRAM was fully committed.** PID 41610 held 14,048 + 12,912 MiB serving the daily
driver (`Qwen3.8-27B-Q6_K`, 262144 ctx, VBR KV, MTP draft), started at 10:05:23.

Before stopping it: its exact argv was captured from `/proc/41610/cmdline` into
`restore_daily_driver.sh`, preserving argument boundaries rather than reconstructing from a
space-joined string (the model path contains a space and `--chat-template-kwargs` carries JSON).
VRAM was confirmed drained to 0 MiB on both cards by polling, not inferred from the kill
returning. The stop itself re-read that PID's own `cmdline` at signal time to confirm identity,
rather than matching a pattern against a process list.

**Tenth instrument defect: I concluded the endpoint could not restart itself, and I was wrong.**
I ran `systemctl --user cat apollo-wake-proxy | head -20`, saw no `WP_START_CMD`, noted that
`wake_proxy.py` defaults it to `""`, and concluded the proxy ran in *managed mode* and that
"nothing would have restarted it." `WP_START_CMD` is in fact set, on **line 28** of the same unit
-- past the 20 lines I read. The proxy's own log is unambiguous:

```
2026-09-19T10:05:23 start: launching llama-server      <- the driver I called "hand-launched"
2026-09-19T11:05:24 start: launching llama-server      <- automatic, 2 s after the gate exited
```

So the driver was started by the **proxy**, not by a person; `session-922.scope` was the proxy's
own ssh session, and the proxy restored the endpoint on its own within 30 s of the gate finishing
(`start: /health OK after 28s`). The restore script was never needed and lost a port-bind race,
which is why `restore.log` records `couldn't bind HTTP server socket`. Harmless, and the endpoint
was down for 17 minutes rather than indefinitely.

Same shape as the day's other defects: **a truncated view treated as the whole**, with a
plausible-looking second source (the code default) mistaken for confirmation.

**The operational consequence is real and applies to the cells, not to this run.** The proxy
restarts llama-server whenever an inference request arrives and it is not serving. Nothing called
that path during the gate's 17 minutes, so the gate ran uncontested by luck rather than design.
The five-cell batch is roughly 85 minutes of GPU occupancy, and a single proxied request during it
would have the proxy try to load a 22.9 GB model into VRAM a cell already owns. **The proxy must
be stopped for the duration of the cell batch**, which is honest rather than merely convenient:
while the ladder owns both P100s the endpoint genuinely cannot serve.

**The node sleeps on idle.** At the start of this work `.73` was 72 seconds from S3 suspend
(`idle_seconds` 1728 of 1800). `/wake` does **not** reset that clock -- it only counts requests
through the proxy. `/keepalive` does, and a recorded-PID keepalive loop held the node for the
duration.

## Instrument defect (ninth today)

My first completion waiter reported **"GATE FINISHED after 20s"**, which was false; the run had 16
more minutes to go. The check was:

```
R=$(ssh ... 'grep -c MARKER file 2>/dev/null || echo 0')
[ "${R:-0}" != "0" ] && echo FINISHED
```

`grep -c` prints `0` **and exits 1** when there are no matches, so `|| echo 0` also fired. `R`
became `"0\n0"`, which is not equal to `"0"`, so the guard passed on its first poll. Rewritten as
`grep -q MARKER && echo DONE`, tested against the real file.

Same shape as the day's other defects: **a derived check laundering a raw value.** It was caught
only because `env.txt` contained no `GATE_RUN_FINISHED` line when I went to read the result.

A second, harmless one worth recording so it is not re-diagnosed later: **the run log appeared
frozen at 1528 bytes for seven minutes.** That is stdio buffering -- stdout redirected to a file is
fully buffered, and the 1528 bytes already present were stderr warnings. Log growth is not a
progress signal for this binary. Process state (`D` for disk sleep), `/proc/<pid>/io read_bytes`
and GPU utilisation are.

## Next

1. ~~Run the P-L0 gate~~ -- **done, PASS.**
2. Delete the 29 GB Q8_0 from `.73` (the panel needs 45.4 GB more).
3. Transfer the four outstanding models, hashing **both ends** per file.
4. Run the five stock-GGUF cells.
5. Bonsai cells need the `PrismML-Eng/llama.cpp` fork built -- the only build work left.

Raw log: `logs/gate_pl0_run.log`. Environment: `logs/gate_pl0_env.txt`.

## Open obligation

A keepalive loop (`/tmp/ladder_keepalive.pid`) is holding `.73` awake, because `/keepalive` is the
only thing that resets the proxy's idle clock and neither an ssh session nor a `sha256sum` counts
as busy. It is an infinite loop. **It must be killed when the ladder finishes, and the proxy
restarted in the same breath** -- if the proxy is stopped for the cell batch and the keepalive is
left running, nothing at all can suspend the node, which is roughly 110 W in a room that is
already managed for heat. That is the exact cost the proxy exists to avoid.
