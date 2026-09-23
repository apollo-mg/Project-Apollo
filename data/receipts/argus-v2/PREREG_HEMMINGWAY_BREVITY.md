# Prereg — is Hemmingway terse by nature, or better at following a brevity instruction?

**Written 2026-09-22, before any arm ran.**

**Prior art checked:** `ledger_precheck.py "verbosity system prompt brevity instruction following
terse reply length SOUL" --deep` -> `argus-v2/RESULT_HEMMINGWAY_VS_STOCK.md` (the finding this
follows up), INDEX L43 (UkisAI's Swift brevity tune thinks 26 % less on false premises and 20 % more
on answerable items, i.e. brevity spent unevenly by item type), INDEX L50 (verbosity instructions
transfer fully between system block and user turn).
**What this adds:** the Hemmingway result showed 0.77x reply length, but both arms carried a
`SOUL.md` instructing brevity. No existing receipt separates a model's intrinsic register from its
compliance with a length instruction.

## The question

Under the brevity prompt, Hemmingway's replies were 0.77x stock's (CI 0.68-0.87). Two stories fit:

- **intrinsic**: the tune writes shorter regardless, so the ratio stays near 0.77x with no prompt
- **compliance**: the tune obeys "match the length of your reply to the weight of the ask" better,
  so without the prompt the ratio moves toward 1.00x

## Design: 2 x 2, all cells fresh

| | brevity `SOUL.md` (sha `36c1f5a2`) | no `SOUL.md` (Hermes default identity) |
|---|---|---|
| stock `Qwen3.8-27B-Q5_K_M` | S+ | S- |
| `Altworld_Hemmingway-1-Q5_K_M` | H+ | H- |

All four cells run fresh under the **current harness**: bubblewrap sandbox, stripped reset, browser
deny rules, loop hard-stop. So they are matched to each other and **not** to the earlier unsandboxed
run. Each cell gets its own `make_fixture.sh` fixture (concurrent arms must not share a world).

`.194`, `buun build_sm60_0920`, `-sm tensor -c 65536 -ctk f16 -ctv f16 -np 1`,
`reasoning_effort: medium`: the reference `start_arm.sh` configuration. Stock on GPUs {0,1}
`:8084`, Hemmingway on {2,3} `:8085`, concurrent. Sampling as in the original run (both GGUFs
embed temp 1.0 / top_k 20 / top_p 0.95; `min_p` 0.05 inherited and shared), **verified from `/props`
at every launch**.

**2 reps per cell** on all 40 items. Sized from the existing data by resampling: a full
disappearance of the effect (0.77x -> 1.00x) is detected at z ~ 3.8; one rep would give z ~ 2.2. A
*half* move (0.77x -> ~0.88x) is borderline at z ~ 1.9 and must be reported as such, not as a
detection.

**Order counterbalanced and servers restarted per phase** (`[[server-uptime-is-a-variable]]`):
rep 1 runs brevity-prompt then none; rep 2 runs none then brevity-prompt.

## Analysis, fixed now

Per item: geometric mean over reps of `reply_chars`; log ratio H/S within each prompt condition.
- **R+** = mean log ratio under the brevity prompt, **R-** = without it (paired by item)
- **interaction** = R- minus R+, per item, paired t and Wilcoxon

Secondary, same method: `think_chars` and tool calls. **Wall time is NOT analysed.** The 9B gate
runs concurrently on the desktop, where the drivers and agents live, so `secs` is confounded by
host load.

Exploratory, following the Swift receipt: does Hemmingway's reasoning cut concentrate on particular
families (premise, unsat)?

Judgement pass rates are reported per cell but **not** tested for a prompt effect: 2 reps cannot
resolve anything smaller than the ~10-point floor.

## Predictions, committed before data

| id | prediction | conf | falsifier |
|---|---|---|---|
| **B1** | under the brevity prompt, H/S reply ratio replicates below 0.90x | 0.85 | R+ >= 0.90x or CI includes 1 |
| **B2** | removing the prompt lengthens STOCK's replies (S-/S+ > 1.2x) -- the prompt works at all | 0.75 | <= 1.2x |
| **B3** | without the prompt, Hemmingway is still terser than stock (R- CI excludes 1.00x) | 0.55 | CI includes 1.00x |
| **B4** | the gap narrows without the prompt (interaction > 0, i.e. part compliance) | 0.50 | interaction <= 0 |
| **B5** | Hemmingway's reasoning reduction is uneven across families (Swift pattern) | 0.40 | reductions within +/-10 % across families |

**The decision:** B3 true and B4 false is **intrinsic**. B3 false is **compliance**. B3 and B4
both true is **both**, with the split read off the interaction estimate.


---

## AMENDMENT — mid-run harness change at 21:39:32 (credential environment variables stripped)

At **21:39:32** the sandbox wrapper began removing every credential-named environment variable before
starting the agent. The wrapper runs per scenario, so every scenario from 21:39:32 onward ran without
them. Nothing else changed.

**Why:** the driver passes the caller's entire environment to the agent, and it carried a Claude
Code session token, while the sandbox shares the network. **What had happened before 21:39:32:** in the concurrent 9B gate, MiMo ran
`env | grep` four times during the 9B gate, twice with patterns including `token`. Its only
network activity was two **unauthenticated** status-code probes (`gmail.googleapis.com` and
`www.google.com`), with no credential in either, confirmed from Hermes's session store. The token
value appears nowhere on disk in the run outputs, fixtures or receipts.

**Effect on the measurement:** none expected. No model's task can use an environment secret, and
no scored action depends on one. Rows before and after 21:39:32 are pooled; this is recorded so the change
is not invisible. Verified that both running experiments kept producing normal verdicts afterwards.
**Residual:** the network is still shared. A model can reach the internet; with secrets stripped
and the home directory hidden it has little to carry. `--unshare-net` plus a forwarder for the
model port is the next hardening step.
