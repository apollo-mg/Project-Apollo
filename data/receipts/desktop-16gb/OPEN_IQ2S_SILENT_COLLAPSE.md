# ~~OPEN~~ RESOLVED TO THE COMPONENT: it is the VBR KV path — see `RESULT_VBR_COLLAPSE_CONTROLLED.md`

> **An f16-KV control settled this.** Identical model, items, budget and harness; KV codec the
> only variable. f16 answered all ten items in 422-706 characters and stayed healthy; VBR
> collapsed on the **first** item and its canary was dead afterwards. The component is
> identified; the mechanism inside VBR is still unknown. The elimination log below is kept
> because it records eleven hypotheses that were all wrong in the same way — every one
> assumed VBR was involved without testing it, which the control did in twenty minutes.

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

## Round 2 — three more hypotheses dead, still no mechanism

| # | hypothesis | test | result |
|---|---|---|---|
| 8 | overthinking, not collapse (T2-01 produced 2,861 real tokens once) | dump full response bytes | **collapse confirmed** — `bang_frac=1.00`, content empty, 3072 `!` |
| 9 | `reasoning_effort=medium` curbs it | tier 2 at medium | **0/10, identical** — effort is irrelevant |
| 10 | a generation-depth threshold near 2048-3072 | fresh restart per depth, canary after | **FALSIFIED** — collapsed at **1536**, below every depth that had survived |
| 11 | VBR auto-budget varying by startup free VRAM | compare budget across 6 server logs | **4304-4312 MiB in ALL of them**, healthy and collapsed alike |

**Eleven hypotheses eliminated. No mechanism identified.**

### The one clean signal that keeps holding

Every collapse has been **total and persistent**: once a server emits `!`, every subsequent
request does, until restart. And a **freshly started server answers correctly** — until at
some point it does not. Onset is not tied to request count, prompt, item, depth, effort, or
budget, all of which were tested directly.

### Honest assessment of this hunt

**I thrashed.** Eleven ad-hoc hypotheses, each plausible, each killed by a control, several
built on a single unverified sample. Two specific errors worth keeping:

1. **Reasoning from n=1.** Ten items showed `NO-ANSWER (truncated)`. I dumped **one**, saw
   `!`, and built four experiments on it. Later one item produced 2,861 real tokens and I
   swung to "overthinking" — also from one sample. The byte-level dump that settled it took
   two minutes and should have been the *first* step, not the tenth.
2. **Mistaking untested for eliminated.** The onset test rotated 5 of 10 tier-2 items and I
   recorded "items eliminated". It covered half.

**The disciplined move now is to stop probing ad hoc.** The next action should be the control
that has never been run, not a twelfth guess.

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

1. **f16-KV control — STILL NEVER RUN, and now clearly the only disciplined next step.**
   Identical model, identical sequence, `-ctk f16 -ctv f16`. If it collapses too, VBR is
   innocent and this is IQ2_S weights (or the HIP path) — which changes the protocol's whole
   recommendation. If it does not, VBR is implicated by elimination rather than by a guess.
   **Every hypothesis tested so far assumed VBR was involved without ever checking.**
2. **Longer soak with a canary every N requests**, to establish whether onset is a threshold
   or a probability.
3. If VBR is implicated, re-test with `VBR_BUDGET_MIB` **pinned** rather than auto — the auto
   budget derives from `hipMemGetInfo`, which this same session measured to be wrong by
   2.4 GiB on this machine.
