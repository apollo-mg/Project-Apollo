# Sampling for Argus agent runs — pinned, and why

Qwen3.8-27B card, and we run with reasoning ON (`reasoning_effort: medium`,
`preserve_thinking` default), so **Thinking Mode** is the matched profile:

| param | card (thinking) | card (instruct) |
|---|---|---|
| temperature | **1.0** | 0.7 |
| top_p | **0.95** | 0.80 |
| top_k | **20** | 20 |
| min_p | **0.0** | 0.0 |
| presence_penalty | **0.0** | 1.5 |
| repetition_penalty | **1.0** | 1.0 |

The card also confirms `xhigh` is the **default** `reasoning_effort` — independently matching
what AFM-23 found by measurement. We pin `medium` deliberately.

## What was wrong before this file existed

1. **temp 0.6 / top_p 0.95 / top_k 20** — these are the **Qwen3.5/3.6** values. Carried over
   out of habit; not 3.8's numbers.
2. **`min_p = 0.05`** — llama.cpp's default, never chosen by anyone, silently truncating the
   tail on *every agent run we had done*. The card says 0.0. Found only because the card text
   was read closely, not because anything failed.

Both are the same class of error: a parameter nobody selected doing real work. The
`reasoning_effort` pin was audited carefully; the sampler chain was not audited at all until
`/props` was actually queried.

**Always read `/props` after launching. The command line is what you asked for; `/props` is
what you got.**

## The two arms

Everything identical except temperature, pinned SERVER-side so it appears in `/props` and in
the process line rather than being inherited.

- **Arm A — temp 0.6.** Off-card, deliberately. Below the card's thinking-mode value, so it
  bounds how much of the verdict flipping is sampling temperature.
- **Arm B — temp 1.0.** The card's thinking-mode value. The reference.

Both: `top_p 0.95, top_k 20, min_p 0.0, presence 0.0, repeat 1.0`.

**Reading:** if the flip rate is similar in both arms, sampling temperature is not the driver
and trajectory branching is — one early tool call deciding the whole outcome. If it drops
sharply at 0.6, temperature is a lever a deployer could actually pull.

Not temp 0: it does not buy determinism on this hardware (HA-04 was bistable 35/100/100/35 at
temp 0) and nobody deploys there.
