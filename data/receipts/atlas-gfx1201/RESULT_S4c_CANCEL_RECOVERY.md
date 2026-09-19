# Result -- RST charter (c) cancel/recovery: PASSES, and the utilization knob is inert

**2026-09-18.** Charter (c) of S4 in Avarok-Cybersecurity/atlas#1126, RX 9070 XT (16 GB, desktop
co-resident ~2.2 GB), Ornith-1.0-9B-NVFP4, SCALE 1.7.1.

Charter: *"kill the client 2 s into a 2494-token prefill, and mid-stream in a 512-token decode,
5 times each."* Gate: *"the next request succeeds; VRAM returns to within 10 percent of
baseline."*

## Charter (c): PASS

Run at **`--max-seq-len 2560`** rather than the PRD's 4096. That deviation is forced, measured,
and explained below. Everything else is per the charter.

| phase | iterations | next request succeeds | worst VRAM excursion |
|---|---|---|---|
| client killed 2 s into prefill | 5 of 5 | **5 of 5 OK** | +1.1% |
| client killed mid-stream in decode | 5 of 5 | **5 of 5 OK** | +1.1% |

Baseline 13.634 GB, final 13.770 GB, **+1.0%** against a 10% gate. Server alive at the end. The
decode kills landed genuinely mid-stream, cutting after 129-131 streamed SSE chunks each.

**Atlas's cancellation handling is clean.** Ten abrupt client disconnects, five of them during
chunked prefill and five during active token streaming, and VRAM never moved more than 1.1% from
baseline. Nothing leaked and nothing wedged. Client kills were by exact PID (the harness and its
target are both `curl`, so a pattern kill would have taken out the verification request too).

## The finding: `--gpu-memory-utilization` does not do anything here

Charter (c) failed twice before this run, both times because the server was terminated by its own
OOM watchdog rather than by anything the charter did. Chasing that produced the more useful
result.

**Utilization ladder at seq 4096, 30 s idle observation each:**

| `--gpu-memory-utilization` | min free | KV tokens granted | outcome |
|---:|---:|---:|---|
| 0.85 | 1701 MB | 4128 | watchdog kill |
| 0.80 | 1761 MB | 4128 | watchdog kill |
| 0.75 | 1761 MB | 4128 | watchdog kill |
| 0.70 | 1722 MB | 4128 | watchdog kill |

**Identical KV allocation and effectively identical free memory across the whole range.** The
pledge is a ceiling that was never binding: at 0.85 the server reported *"util pledge honored:
11.1 GB tracked live within the 13.5 GB budget (2.5 GB pledge headroom)"*. Actual usage is 11.1 GB
whatever the ceiling says, so lowering the ceiling to 11.1 GB changes nothing except removing
headroom.

This matters for the PRD directly: **`RESULT_S3_SERVE.md` recommended lowering utilization for
16 GB parts. That recommendation is wrong and I am withdrawing it.** It would have had no effect.

**Sequence length is the actual lever**, because the buffer arena scales with it:

| `--max-seq-len` | buffer arena | min free (idle) | outcome |
|---:|---:|---:|---|
| 4096 | 1.36 GB | ~1700 MB | killed at idle, before any request |
| 3072 | 1.05 GB | 2092 MB | survives idle, **dies during a 2272-token prefill** |
| 2560 | 0.90 GB | 2259 MB | survives everything, charter passes |

The seq-3072 failure is worth quoting because of how narrow it is:

```
16:25:05  Session: 2272 prompt tokens, chunked prefill start
16:25:08  OOM watchdog: GPU free memory critically low: 2010 MB (threshold: 2048 MB) [1/3]
16:25:10                                                2023 MB [2/3]
16:25:12                                                2025 MB [3/3]
16:25:12  OOM watchdog: 3 consecutive readings below threshold. Terminating.
```

A prefill of that size costs roughly 80 MB of transient headroom, which puts seq 3072 **23 to
38 MB** under the threshold. Not a design margin -- a rounding error. Free about 250 MB anywhere
on this board and seq 3072 passes.

## What this says about the configuration, not the code

The watchdog threshold is 2048 MB and the desktop session holds about 2.2 GB. Atlas is behaving
correctly at every step: it sizes honestly via sysfs, it warns before it overcommits, and it
terminates rather than freezing a machine whose display it is sharing. The constraint is that a
16 GB board minus a 2.2 GB desktop minus a 2.048 GB safety floor leaves about 11.7 GB, and
Ornith-9B at seq 4096 wants more than that.

**Two ways forward, and the choice is not mine to make:**

1. **Free the desktop's VRAM** by driving the box headless from another machine. This restores
   roughly 2.2 GB and makes seq 4096 comfortable. It is also the answer charter (f) needs anyway,
   since (f) gates on flat VRAM and a live compositor cannot give that.
2. **Run the remaining charters at reduced seq** and document each deviation. Cheaper, but (d)
   and (f) both want sustained load, and their numbers would not be comparable to an R9700 run.

`AVAROK_DISABLE_WATCHDOGS` exists and would let seq 4096 run. **Not used, and not recommended.**
The watchdog's stated purpose is preventing a system freeze on a card driving a display, and the
measurements above show the margin it is protecting is real.

## Instrument defect

The gate arithmetic in `charter-c.sh` used `gsub("+","",p)` to strip the sign from a percentage
like `+1.1`. In awk `"+"` is a bare regex with a missing operand, so the whole line failed and the
worst-excursion figure printed as an empty string. Caught because the output was visibly
malformed rather than subtly wrong. Fixed to `p=$6+0` and an absolute value, which is what it
should have been.

Worth noting that the first two charter (c) runs would have reported "FAIL, 10 of 10" with no
indication that the server had died before the first kill. The per-iteration VRAM column is what
made it obvious: 2.2 GB where the baseline was 13.9 GB is not a leak, it is an absent model.

## Status of S4

| charter | status |
|---|---|
| (a) coherence | PASS -- 9 of 10 canaries, known exception |
| (b) VRAM boundary | done; gate needs rewording for a back-pressure architecture |
| (c) cancel/recovery | **PASS at seq 2560**, 0 failures, +1.0% VRAM |
| (d) sustained decode, 10 min | blocked on the headless decision |
| (e) REST conformance | PASS -- 9 PASS / 1 FAIL, known defect |
| (f) concurrency soak, 30 min | blocked on the headless decision |
