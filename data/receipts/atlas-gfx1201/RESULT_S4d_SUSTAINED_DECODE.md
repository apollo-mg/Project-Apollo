# Result -- RST charter (d) sustained decode: 10 minutes, no drift, no throttling

**2026-09-18.** Charter (d) of S4 in Avarok-Cybersecurity/atlas#1126. RX 9070 XT (16 GB),
Ornith-1.0-9B-NVFP4, SCALE 1.7.1, **seq 4096 / batch 1** (the PRD's configuration -- reachable
because 1.05 GB of desktop VRAM was freed first; see the note at the end).

Charter: *"10 minutes of back-to-back 256-token generations; sample GPU temperature, power and
clocks from hwmon every 10 s."* Gate: *"tok/s drift and any throttling reported, not hidden
(ambient heat is a stated condition of this box)."*

## Throughput: flat

| | value |
|---|---|
| requests completed | **163**, all exactly 256 completion tokens |
| errors | **0** |
| first 60 s median | 69.58 tok/s (n=17) |
| last 60 s median | **69.70 tok/s** (n=16) |
| **drift** | **+0.17%** |
| overall | median 69.68, min 66.41, max 69.81 |

A spread of 3.4 tok/s between the slowest and fastest request across ten minutes, and the last
minute is marginally *faster* than the first. There is no thermal decay to report.

## Hardware: hot, but never throttled

60 hwmon samples at 10 s intervals.

| metric | start | max | final | median |
|---|---:|---:|---:|---:|
| edge temp | 34 C | 49 C | 49 C | 48 C |
| junction temp | 37 C | **76 C** | 75 C | 75 C |
| memory temp | 58 C | **82 C** | 82 C | 80 C |
| board power | 53 W | **383 W** | 383 W | 324 W |
| sclk | 1448 MHz | 3302 MHz | 3203 MHz | **3219 MHz** |
| fan | 1526 rpm | 3438 rpm | 3387 rpm | 3371 rpm |
| VRAM free | 2844 MB | -- | 2776 MB | 2752 MB |

**No throttling.** sclk held between 3203 and 3302 MHz for the entire run, which is boost
territory; the driver never dropped a DPM state. Junction peaked at 76 C against an RDNA 4 limit
far above that, and memory at 82 C likewise. The charter's parenthetical about ambient heat is
well taken -- the room is running a 95 F heat index today -- and the card simply did not care.

**VRAM was flat**: 2844 MB free at the start, 2752 MB median, 2776 MB at the end. A 92 MB band
over ten minutes of continuous load, with a live desktop as co-tenant. That is a good sign for
charter (f)'s flat-VRAM gate, though (f) still needs the compositor gone to be measured honestly.

## Open question: 69.7 tok/s here vs 78-80 on the R9700

PR #1107 reports *"78-80 tok/s decode"* for this model on the Radeon AI PRO R9700. This run
medians **69.68**, about 13% lower.

**Not claimed as a hardware difference**, and there is a specific reason to be careful: the two
boards are compute-identical (both 64 CU / 32 WGP, both reporting `sm_count = 32`) and both are
640 GB/s class. So a 13% gap has no obvious architectural explanation, which makes it much more
likely to be a measurement difference than a silicon one. Candidates, none tested:

- **Co-tenant desktop.** plasmashell, Discord and the Claude desktop app were all live on the card
  during this run, doing periodic compositing work. A few percent of decode is plausible.
- **Different harness.** My loop measures wall-clock around a complete non-streaming HTTP request,
  so it includes prefill of a short prompt, scheduling and JSON serialisation. If their figure is
  a decode-only rate from server-side instrumentation, it would read higher on identical silicon.
- **Unknown prompt and sampling.** Theirs is unstated.

The cheap discriminator is to re-run this charter with the display manager stopped. If the gap
closes, it was the co-tenant; if it does not move, the harness difference is the explanation and
the two numbers were never comparable. That run is queued behind the headless setup.

## Note on how seq 4096 became reachable

Charter (c) established that this board could not hold 2048 MB free at seq 4096 with a ~2.2 GB
desktop resident, and that `--gpu-memory-utilization` is inert as a remedy (see
`RESULT_S4c_CANCEL_RECOVERY.md`). Closing a browser freed 1.05 GB, which moved free memory at
seq 4096 from about 1700 MB to **2845 MB** and made the PRD's stated configuration work without
any deviation.

Per-process VRAM before and after, from `/proc/*/fdinfo`:

```
before: chrome 0.68 + plasmashell 0.46 + Discord 0.17 + Hermes 0.15
        + systemsettings 0.13 + claude-desktop 0.13 + portal 0.13 + misc 0.14 = 1.99 GB
after:  plasmashell 0.45 + Discord 0.15 + claude-desktop 0.13 + portal 0.13 + misc 0.08 = 0.94 GB
```

Worth stating plainly for the PRD: **on a 16 GB board the desktop is not a rounding error, it is
the difference between the reference configuration running and not running.** A browser is worth
more VRAM than the entire KV cache budget at seq 2560.

## Status of S4

| charter | status |
|---|---|
| (a) coherence | PASS -- 9 of 10 canaries, known exception |
| (b) VRAM boundary | done; gate needs rewording for a back-pressure architecture |
| (c) cancel/recovery | PASS -- 0 failures, +1.0% VRAM |
| (d) sustained decode | **PASS -- +0.17% drift, no throttling, 0 errors in 163 requests** |
| (e) REST conformance | PASS -- 9 PASS / 1 FAIL, known defect |
| (f) concurrency soak | remaining; needs the desktop headless for its flat-VRAM gate |

Data: `logs/charter-d/requests.tsv` (163 rows), `logs/charter-d/hwmon.tsv` (60 rows).

---

# Addendum -- the headless re-run: the co-tenant hypothesis is dead

**2026-09-18, later.** Charter (d) re-run with the display manager stopped
(`systemctl stop plasmalogin`), freeing 1.02 GB and taking free VRAM from 2845 to 3911 MB.
Server restarted fresh first, so both runs start from equal uptime. Identical parameters;
the only variable is the desktop.

| | with desktop | headless | delta |
|---|---:|---:|---:|
| requests | 163 | 160 | -1.8% |
| **median tok/s** | **69.68** | **68.50** | **-1.69%** |
| mean tok/s | 69.64 | 68.56 | -1.55% |
| min tok/s | 66.41 | 67.30 | +1.34% |
| max tok/s | 69.81 | 69.83 | +0.03% |
| drift | +0.17% | +0.03% | -- |
| errors | 0 | 0 | -- |
| junction max / median | 76 / 75 C | 76 / 74 C | -- |
| power max / median | 383 / 324 W | 374 / 322 W | -- |
| sclk median | 3219 MHz | 3220 MHz | -- |

**Headless is not faster. It is 1.7% slower**, which is within run-to-run variation and in the
opposite direction from the hypothesis. Removing the compositor bought VRAM headroom and nothing
else measurable.

So the 69.7 vs #1107's 78-80 tok/s gap is **not** explained by the co-tenant desktop, and the
harness difference becomes the standing explanation: this loop times a complete non-streaming
HTTP round trip (prefill of a short prompt, scheduling, generation, JSON serialisation), while a
decode-only rate read from server-side instrumentation would report higher on identical silicon.
The honest conclusion is that the two figures were never measuring the same quantity, not that
one board is slower than the other. Settling it needs their harness, not more runs of mine.

## A correction to my own reasoning, not to a number

I argued that charter (f)'s flat-VRAM gate required a headless box because a live compositor
would drift too much. The data says otherwise: the VRAM band across ten minutes was **106 MB with
the desktop up and 94 MB headless**. A 12 MB difference. Charter (f) would very likely have passed
its flatness gate either way.

Going headless was still the right call, but for the other reason: **capacity, not stability.**
Free VRAM went from 2845 to 3911 MB, and that is what made seq 4096 reachable at all after
charter (c) found the board could not hold the watchdog's 2048 MB floor with a 2.2 GB desktop
resident. Right conclusion, partly wrong reason, and the wrong half is worth recording because it
would have justified a headless requirement that the evidence does not support.

## Largest batch that boots (probed for charter (f))

| `--max-batch-size` | boots | survives | KV tokens | free VRAM | overcommit warning |
|---:|---|---|---:|---:|---|
| 8 | yes | **yes** | 32912 | 2666 MB | no |
| 16 | yes | **no** | 62832 | -- | yes |
| 32 | yes | **no** | 36576 | -- | yes |

Batch 16 and 32 both reach *"Server live and ready"* and are then terminated by the OOM watchdog
about four seconds later at 1350 MB free:

```
19:38:00  OOM watchdog: GPU free memory critically low: 1350 MB (threshold: 2048 MB) [1/3]
19:38:01  Server live and ready at 127.0.0.1:8081
19:38:02                                            1350 MB [2/3]
19:38:04                                            1350 MB [3/3]
19:38:04  OOM watchdog: 3 consecutive readings below threshold. Terminating.
```

Note the first watchdog reading precedes the readiness announcement.

**This is a second charter-language problem, the same class as (b)'s missing refusal.** Charter (f)
says "the largest batch that boots". Batch 32 *boots*. It answers `/v1/models`, announces itself
live and ready, and dies three seconds later. A harness that polls for readiness and proceeds
would select 32 and then measure a corpse -- which is exactly the "readiness probes lie" failure
mode, arriving from the charter's own wording. The usable answer on this board is **8**, and the
criterion should read "boots and holds" or carry a dwell time.

---

# Addendum 2 -- thinking off: the last controllable variable, also eliminated

**2026-09-18.** Third run of charter (d), identical except `chat_template_kwargs:
{enable_thinking: false}`, matching the default in TheTom's kit scripts. Headless, seq 4096,
batch 1, fresh server.

| configuration | n | median tok/s | mean | min | max | drift |
|---|---:|---:|---:|---:|---:|---:|
| thinking ON, desktop resident | 163 | 69.68 | 69.64 | 66.41 | 69.81 | +0.17% |
| thinking ON, headless | 160 | 68.50 | 68.56 | 67.30 | 69.83 | +0.03% |
| **thinking OFF, headless** | 163 | **69.57** | 69.55 | 68.38 | 69.75 | +0.06% |

**Total spread across all three: 1.18 tok/s.** Every configuration sits at 68.5-69.7, and none
approaches #1107's 78-80.

Both variables available to test from this end are now eliminated:

- **Co-tenant desktop:** removing it changed throughput by -1.7%, in the wrong direction.
- **Thinking mode:** disabling it changed throughput by +1.6% from the headless baseline, landing
  back where the first run was. A token is a token for decode rate, as expected, but it needed
  measuring rather than asserting.

Combined with the hardware parity established in `RESULT_S4ae_COHERENCE_REST.md` -- both boards
Navi 48, 64 CU / 32 WGP, 256-bit GDDR6 at ~640 GB/s, with the 9070 XT holding the *higher* boost
clock (2970 vs 2920 MHz) -- there is no remaining candidate on this side.

**Conclusion: the two figures measure different quantities.** This harness times a complete
non-streaming HTTP round trip: prefill of the prompt, scheduler admission, 256 tokens of decode,
JSON serialisation and transport. A decode-only rate taken from server-side instrumentation
excludes most of that and would read higher on identical silicon. Closing it requires knowing how
the 78-80 was produced; it cannot be settled by further runs here.

Stated for the record so the number is not quoted as a hardware comparison: **69.6 tok/s is this
harness's end-to-end figure, not a claim that a 9070 XT decodes slower than an R9700.** On the
evidence, it should not.
