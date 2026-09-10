# Batching does not rescue Flash-Next for a single user

**Date:** 2026-09-03
**Node:** .194 (quad P100, sm_60), GPUs 0+1 only (`CUDA_VISIBLE_DEVICES=0,1`)
**Build:** `~/buun-llama-cpp/build_sm60_qwen4/bin/llama-server`
**Model:** `Qwen3.8-Flash-Next-UD-Q2_K_XL-00001-of-00003.gguf`
**Flags:** `-c 16384 -ngl 99 -fa on --jinja -np {1,2,4} -fit off -ncmoe 30 -sm tensor --kv-unified`,
`GGML_CUDA_ALLREDUCE=internal`
**Load:** `n_predict=128`, `temperature=0`, `cache_prompt=false`, distinct prompt per concurrent
request (prompt_n=19 each). Server **restarted per leg** (AFM-26 discipline).

## Result

| `-np` / concurrency | per-request tok/s | aggregate tok/s | wall s |
|---|---|---|---|
| 1 | 9.69 | 8.93 | 14.3 |
| 2 | 7.08 | 12.86 | 19.9 |
| 4 | 4.01 | 14.57 | 35.1 |

Verified against raw `timings.predicted_per_second` in every `r*.json`, not the tabulation script.
All requests within a leg returned **identical** tok/s — lockstep continuous batching, as expected.

## Predictions, scored

Logged before the run: *"batching improves aggregate throughput meaningfully while barely touching
per-user latency, and the aggregate gain is sublinear in batch size because expert fetch scales
with distinct experts touched, not with passes."*

1. **Aggregate improves meaningfully** — CORRECT. 1.63x at np4.
2. **Sublinear in batch size** — CORRECT. 4x batch buys 1.63x aggregate.
3. **"barely touching per-user latency"** — **FALSIFIED.** Per-request throughput fell 59%
   (9.69 -> 4.01). A single user at np4 waits 2.4x longer per token. This was not a small miss;
   it is the half that answers the question actually asked.

2 of 3. The falsified clause is the one that matters.

## What it means

**Batching pays when you have a queue, not when you have a conversation.**

- Single interactive user: `-np 1` is strictly best. Batching is a pure loss.
- Four independent queued tasks: 35.1 s versus 4 x 14.3 = 57.2 s serial, a **1.63x** wall-clock win.
  That is the multi-agent case -- Apollo's original design -- not the chat case.
- **The knee is at np2.** np1->np2 buys 1.44x; np2->np4 buys only a further 1.13x. np8 is not
  worth testing for throughput.

Consistent with the host-expert-fetch bottleneck established earlier: if this were GPU-compute
bound, batching would give near-linear aggregate scaling at roughly flat per-request cost, because
concurrent sequences would fill otherwise-idle SMs. Instead aggregate scales sublinearly *and*
per-request degrades -- the signature of a shared bottleneck that batching cannot relieve.
The 1.63x that does appear is the overlap dividend: four prompts touch overlapping experts, so
some fetches amortise. It is not evidence of spare compute.

## Caveats and gaps

- **Clock/power not captured per leg.** The script's `meta.txt` came out empty. Power limit is the
  fleet standard 150 W (`persistence_mode Enabled`); applied SM clock during the run is unrecorded.
  Fix the harness before the next run rather than back-filling.
- np1 here is **9.69 tok/s** against ~12.45 tok/s measured previously for Flash-Next. Different
  config (2 GPUs, `-c 16384`, `--kv-unified`, `n_predict=128` short generation). The three legs are
  internally consistent with each other; **do not** compare this np1 number to the earlier figure.
- Short generations (128 tokens) mean prefill is a non-trivial share of wall time. A long-generation
  batch sweep could show a different aggregate curve.
- K=1 per leg. No repeat, no error bars.

## Harness defects found (both silent)

1. **Bare `wait` waits on the backgrounded `llama-server`.** It never exits, so the script hung
   after the requests completed. Cost ~4 h of idle machine. Fix: collect curl PIDs, `wait "${pids[@]}"`.
2. **A fixed `sleep` is not a teardown.** In the chained TURBO run the next arm died on
   `couldn't bind HTTP server socket`. My first diagnosis -- "the server survived two `pkill -x`
   calls" -- was WRONG: I sampled while the turbo arm was still legitimately serving prompts
   (p5 landed 06:17:42, after my check at 06:16:09). `pkill` worked. The actual defect is that
   `pkill -x llama-server; sleep 2` + `sleep 4` gives llama-server only ~6 s to shut down, and
   releasing 16.75 GiB of VRAM plus joining threads takes longer, so port 8096 was still bound
   when the next arm called `bind()`. Fix: verify the postcondition -- poll until the port is
   actually free, escalate TERM->KILL, refuse to start otherwise.
3. **`kill -0 $!` is invalid after `setsid`.** setsid forks the server and exits, so `$!` is a dead
   PID within seconds and the probe reports "died" for a healthy loading server.

All three are the same error: trusting a command's return, or a fixed delay, instead of checking
the postcondition. Same family as [readiness-probes-lie].

A fourth instance, pointed at my own inspection rather than a script: I twice read the output
directory mid-write and reported a conclusion from it -- first "control never ran, turbo did 2 of
3", then "turbo did 3/3". The truth was 5/5. Counts taken before the completion marker are not
counts. Nothing in this receipt rests on one.

---

**2026-09-03 addendum — this config no longer exists.** These numbers were taken with
`-sm tensor` on qwen4exp using build `7a918624b`. That combination was added to the
`llm_arch_supports_sm_tensor` denylist by upstream PR #27941 (Daniel Han, 2026-09-01) and is
**refused by current buun and current upstream**. The measurements stand as a record of that
binary's behaviour; they are not reproducible on current code, and a rerun needs `-sm layer`.
See [RESULT_META_BACKEND_SEGFAULT.md](RESULT_META_BACKEND_SEGFAULT.md).
