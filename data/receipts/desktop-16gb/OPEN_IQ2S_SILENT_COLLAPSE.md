# OPEN: IQ2_S + VBR on RDNA4 silently collapses into `!` characters — cause unknown

**2026-08-19**, control plane **RX 9070 XT (gfx1201, RDNA4, ROCm/HIP)**, buun `02f8581`
`build_rocm`, `Qwen3.8-27B-AD-IQ2_S.gguf`, `-ngl 99 -c 16384 -ctk vbr -ctv vbr --jinja`.

**Status: reproduced twice, not yet reproducible on demand, cause NOT established.**
Recorded now so the observation survives regardless of whether the mechanism is found.

## The observation

A `llama-server` that answered correctly for an extended session began returning **pure `!`
characters to every request**, including trivial ones it had answered minutes earlier.

```
finish_reason: stop        <- not an error
HTTP 200                   <- not an error
content: ""                <- empty
reasoning_content: "!!!!!!!!!!!!!!..." x3072
```

- **Silent.** No abort, no CUDA error, no warning. `finish_reason: stop`, HTTP 200.
- **Total.** Once it starts, every subsequent request collapses. Tier 1 fell from **5/5 to
  0/5** on the same server.
- **Persistent until restart.** A fresh server answers the same items correctly.
- **Same family as the sm_60 KV collapse** documented in `kv-tensor-split/` (512 `/`
  characters there, `!` here) — degenerate single-character output at HTTP 200.

## Detected by the tier-1 gate, ninety minutes after it was written

`fixture_v0_beta.json` tier 1 is five trivial questions with a 5/5 gate. It printed
`TIER 1 FAIL (0/5) <-- STACK IS BROKEN, stop here`. None of the day's fidelity panels,
throughput benchmarks, or memory accounting would have caught this — the model was still
"running", still fast, still returning HTTP 200.

## Hypotheses tested and ELIMINATED

| # | hypothesis | test | result |
|---|---|---|---|
| 1 | VBR degrade controller reaching a broken tier | count `degrade #` events in server log | **zero degrade events fired** in any run, healthy or collapsed |
| 2 | VBR "degrade order exhausted" warning | compare logs | **appears in HEALTHY servers too**, at startup, 1.38 MiB projection — does not discriminate |
| 3 | the fixture's prompt template | fresh server, template vs plain | **both fine** (`Exact Answer: 8`, 741 chars) |
| 4 | a specific tier-2 item | fresh server, items individually | **all fine** |
| 5 | request count (short) | 30 identical short requests | **all clean** |
| 6 | request count (templated) | 30 fixture-template requests | **all clean** |
| 7 | long generations | 12 generations of 2.5-9.4k chars, **canary after each** | **all clean, canary never died** |

**Seven eliminations, no reproduction.** The two observed collapses both occurred during
`run_fixture.py --tier 2`, but that path sends byte-identical requests to the manual tests
that pass.

## What is NOT eliminated

- Something stochastic — a race or a rare state, where ~50 requests happens to be where it
  lands sometimes.
- An interaction requiring a specific *sequence* not yet reproduced.
- IQ2_S weights independently of VBR — **no f16-KV control has been run.** This is the most
  important missing arm: it would separate "2-bit weights are unstable" from "VBR is
  unstable", and those have completely different consequences.

## Method errors this hunt exposed

**1. A test that only watches its own output cannot detect that it broke the host.**
The first pressure run (14 long generations) reported every request "ok" because it only
checked its own replies for `!` characters. The server was already dead when the next tier-2
run started. **Every soak test needs a canary — a known-good question re-asked periodically —
or it cannot distinguish "my requests looked fine" from "the server still works."**

**2. Three wrong mechanisms in one session, all the same shape.** Compute-bound on Pascal
(falsified by power draw), CUDA graphs (the flag was inert and graphs were already on), and
VBR degradation here (zero events fired). Each time the reach was for the newest or most
interesting component rather than the one the evidence pointed at. **VBR was the shiny thing
and it never fired once.** Logged as a standing bias to check against.

## Practical consequence, independent of cause

**This configuration produced correct output for an extended session and then silently
produced garbage until restarted.** For deployment that is the whole answer, and it is worse
than a configuration that never worked, because this one would be shipped.

It does not retract the positive findings — IQ2_S reasoning was sound, tier 1 passed 5/5
fresh, VBR arms and runs on RDNA4 at 29.5 t/s — but it does mean **a 2-bit 27B on a 16 GB
desktop card is not yet trustworthy unattended**, and any claim otherwise needs a soak test
with a canary before it is made.

## Next steps, in priority order

1. **f16-KV control at matched request count.** Separates weights from KV codec. Highest value.
2. **Longer soak with a canary every N requests**, to establish whether onset is a threshold
   or a probability.
3. If VBR is implicated, re-test with `VBR_BUDGET_MIB` **pinned** rather than auto — the auto
   budget derives from `hipMemGetInfo`, which this same session measured to be wrong by
   2.4 GiB on this machine.
