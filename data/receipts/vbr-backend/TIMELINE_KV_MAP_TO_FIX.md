# The KV map and what happened next — correspondence, not proven causation

**2026-09-03.** Assembled after buun said (Discord, 17:32) *"I've made sure everything runs /
I had someone with an RDNA4 bug yesterday and it was really nice to be able to fix it
locally."* Written to check whether our 2026-08-19 KV map went anywhere.

## Timeline

| date | event |
|---|---|
| **2026-08-19** | `kv-map.html`, `RESULT_TCQ_2BIT_RDNA4.md`, `PREDICTION_STATIC_TIERS.md` written. 8/8 turbo KV configs collapse on gfx1201; Qwen3.5-9B at GQA 4:1 clean. Shared with Tom and buun. |
| 2026-08-28 | buun `2f864b8aa` debug: add RDNA2 performance diagnostic matrix; `49e63fe25` automate issue 108 RDNA2 campaign |
| 2026-08-30 | buun `97474a38b` qwen4: add optimized inference, MTP, and VBR support |
| 2026-08-30 | buun `295850adc` **fix(qwen4): restore Turbo V output in sparse attention** |
| 2026-09-01 | buun `0f6a7267a` **fix(qwen4): unrotate Turbo K after QSA gather** |
| 2026-09-01 | buun `283ba19ed` **vbr: support configurable dynamic entry tiers** |
| 2026-09-01 | buun `65eb44ebc` hip: fix RDNA2 FA occupancy and batch VBR VMM maps |
| 2026-09-01 | `7a918624b` — **the commit our checkout was pinned to** |
| **2026-09-02 17:03** | buun `424c3361e` **hip: fix Turbo KV prefill attention dispatch** |
| 2026-09-02 | buun `cb703be37` server: preserve MTP state across prompt checkpoints |
| 2026-09-03 | our stale-checkout re-test reproduces the August collapse and I mis-report it as "buun HEAD" |

## Correspondence with what the map reported

| map finding (2026-08-19) | buun commit |
|---|---|
| turbo-as-**K** is the worse side — collapses even on a 71-token prompt | `0f6a7267a` fix(qwen4): **unrotate Turbo K** after QSA gather |
| turbo-as-**V** collapses too, at longer prompts | `295850adc` fix(qwen4): **restore Turbo V output** in sparse attention |
| "the `q27` degrade order's **first step is already a turbo tier**, so any budget pressure puts turbo in the cache; no ordering helps when every turbo tier is unsafe — only the f16 entry tier is" | `283ba19ed` vbr: **support configurable dynamic entry tiers** |
| "the trigger is **prompt length**, not generation length, not request count" — on AMD | `424c3361e` **hip: fix Turbo KV prefill attention dispatch** |

**Stated honestly: this is correspondence, not proven causation.** None of these commits cites
the map, buun was running his own RDNA2 campaign in the same window, and he has RDNA4
hardware of his own. What can be said is that every axis the map isolated has a matching fix
landed within two weeks of it being shared, and that the fix closest to our headline finding
landed on 2026-09-02.

## What we got wrong, and it was not the physics

The map's measurements were sound and remain so — the collapse at `7a918624b` reproduced
today, on a better detector than the original. The error was **not re-testing for two weeks**
and then reading a stale remote-tracking ref as HEAD. `git log -1` and "HEAD detached at
origin/master" look identical whether or not anyone has fetched.

**Rule: fetch before calling a commit HEAD.** A pinned engine checkout is a frozen snapshot of
someone else's actively-moving tree, and in this project every `engines/*` directory is one.

## Open

Verification in progress: rebuild at `3823c9eb6` and re-run the identical detector, K>=5 per
cell (the failure is stochastic per poshih in `turboquant#311`). Result -> `RESULT_TURBO_FIXED_AT_HEAD.md`.
