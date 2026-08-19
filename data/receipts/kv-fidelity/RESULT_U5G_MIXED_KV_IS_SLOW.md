# Mixed-type KV is ~27× slower than symmetric at depth — which undercuts our own recommendation

**2026-08-19** (overnight), `.194`, quad Tesla P100 (sm_60), buun `02f8581`,
`Qwen3.8-27B-Q6_K`, 32 chunks at `--n-prefix 16376`. **U5g abandoned after three arms.**
Raw `u5g_partial.log`, per-arm logs `~/u5g_raw/` on `.194`.

U5g was meant to re-run `U5f`'s K-vs-V swap at buun's validated 16k operating point. It could
not finish, and **the reason it could not finish is more useful than the result would have
been.**

## What happened

| arm | K/V | prompts completed | wall time | per prompt |
|---|---|---:|---:|---:|
| A | `q8_0` / `q8_0` — **symmetric** | **32 / 32** | 61 min | **1.9 min** |
| B | `q8_0` / `q4_0` — **mixed** | 7 / 32 | 360 min (**timeout**) | **51 min** |
| C | `q4_0` / `q8_0` — **mixed** | 1 / 32 | 74 min (killed) | ~50 min |

**Arm B did not crash — it hit the script's 6-hour ceiling.** No abort, no OOM, no error in
8,917 lines of log; it simply produced 7 prompts' worth of valid `HAZ` rows in the time the
symmetric arm needed for all 32.

**Mixed-type KV runs ~27× slower per prompt than symmetric at 16k.**

## Why this matters more than the measurement it replaced

`RESULT_U5F_ALLOCATION.md` established — across two independent codec families, with every
confound removed — that **at a fixed KV budget the bits belong on V**, worth 31.7-37.7 % in
decision danger. That recommendation requires an **asymmetric** K/V pair.

**This result says that recommendation may be unusable in practice on this build**, because
the asymmetric configurations it points to are the slow ones. A 27× decode penalty is not a
tradeoff anyone accepts for a 37 % fidelity gain.

The two findings are not in conflict — one is about quality per bit, the other about
throughput — but **quoting the first without the second would be advice that damages the
person who follows it.** That pairing has to travel together.

## Why it was invisible until now

Every prior panel ran at `--n-prefix 128`. `U5f` executed the *same* mixed pairs in ~12
minutes per arm and nothing looked wrong. At 136 tokens the KV cache is ~1 MiB and the slow
path costs nothing measurable; at 16k it dominates. **This is the scope correction biting
again, from the throughput side rather than the fidelity side** — and it is the third time
this campaign that a 136-token result failed to describe behaviour at depth.

## Mechanism — hypothesis, not established

Not measured, and flagged as `AFM-17` risk. buun's tree enumerates a **limited set of
supported mixed KV pairs** in `fattn.cu` (`K=TURBO2_0` with
`V ∈ {TURBO3_0, TURBO4_0, Q8_0, F16}`; `K=TURBO3_0` with `V=TURBO2_0`). `q8_0`/`q4_0` is not
in that list. On `.194` the same tree **aborts** for `q4_0` + turbo pairs
(`BEST_FATTN_KERNEL_NONE`), but these stock mixed pairs evidently **fall back** to a working
slow path instead of aborting. A non-flash attention fallback would scale far worse with
context, which fits the observed 1.9 → 51 min/prompt jump between 136 tokens and 16k.

**To establish it:** profile one mixed and one symmetric arm at the same depth and compare
kernel dispatch. Not done.

## What is salvageable

- **Arm A completed and is valid**: `q8_0`/`q8_0` at 16k, 32 prompts —
  `med_KL 0.000039, med_R 0.3322, mean_R 0.4703, cvar95_R 9.6360, flip 0.0017`.
  Against the same arm at 136 tokens (`mean_R 0.1654, cvar95 3.3529`) that is **2.8× more
  decision danger at 120× the depth**, with the `cvar95/mean` ratio holding at **20.49**.
- **The depth-vs-fidelity question is still open.** Answering it needs either a symmetric-only
  panel at 16k, or a mixed panel with a far longer budget and fewer prompts.

## Corrective for the harness

The script reported arm B as `FAILED:` with an empty reason, because it greps for
`SUMMARY` and prints the first error-like line — and a timeout produces neither. **A timeout
must be reported as a timeout.** Any future panel should capture the exit status and
distinguish *aborted*, *timed out*, and *produced no summary*, because those three have
completely different meanings and only one of them is a bug in the code under test.
