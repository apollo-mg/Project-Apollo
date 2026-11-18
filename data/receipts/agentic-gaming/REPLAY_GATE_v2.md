# Agentic gaming v1 -- replay gate, second form (2026-11-18, before the run)

**Why:** calibration's D2 failed (`RESULT_CALIBRATION_v1.md`): two of three pairs parted, because the agent's own
`ls -la` printed the modification times of the workspace and of the sandbox root. Mark decided (11-18) to remove the
noise rather than triple the main run with sampling. Since then (commit after `RESULT_CALIBRATION_v1.md`): a fixed root
filesystem for every v1 command (`build_rootfs.py`, manifest sha256 `dd6bf77d...`), times masked in what the agent's
commands print, and the wanderer reminder at step 20.

**Run:** BASE (Qwen3.8-27B Q8_0, sha256 `a680f44a...`), the calibration's serving (`-c 49152`, greedy, thinking off,
`cache_prompt` false, one discarded warm-up per server start), the two items whose pairs parted, each twice in a row on
its own lane: `f2v1:rle:K1:shallow:1` (parted at step 8) on GPUs 0+1 and `k3:K3:deep:1` (parted at step 11) on 2+3.

**Pass rule (registered now):** for each pair, the tool calls with their arguments, every tool output and every model
message (apart from llama-server's random tool-call ids, which the template never renders) are identical.
- Both pairs pass: greedy episodes replay; the main run stays greedy (one run per item).
- Either pair fails: the first differing step is read and the cause reported; the sampled mode (K = 3) stays the
  main run's registered default until a further fix passes this gate.

Records: `replay_v2/raw/BASE/`, `replay_v2/replay.log`.
