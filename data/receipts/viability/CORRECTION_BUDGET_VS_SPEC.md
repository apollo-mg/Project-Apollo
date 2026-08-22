# Correction — our `n_predict` was 2.3 % of the budget the vendor specifies

**2026-08-22.** Mark found the **Best Practices** section of the Qwen3.8-27B card. It specifies:

> *Reasoning Content: set the maximum output length to **262,144** tokens. Final Response:
> **131,072** tokens.*

**Every fixture run used `n_predict = 6,144` — 2.3 % of the reasoning budget the model is
designed around.** `AFM-24` exists precisely for this (a negative claim is only as wide as the
envelope tested); this names the envelope the vendor intended.

## What survives, what does not

| claim | status | why |
|---|---|---|
| `xhigh` costs **5.85×** `medium` (76,536 vs 13,073 chars) | **SURVIVES** | both arms ran the same budget; `medium` finished comfortably. The ratio measures divergence, not the cap |
| `xhigh` gives **no accuracy benefit** (8/8 both efforts; 24/24 on hard items) | **SURVIVES** | every one of those completed; no truncation involved |
| `medium` is **stable across seeds**, `xhigh` is not | **SURVIVES, caveated** | `medium`'s 16/16 identical is real. Part of `xhigh`'s instability is genuine verdict flips (`CAL-U4`/`CAL-U5` ABSTAINED↔ANSWERED-WRONG), part is truncation |
| `xhigh` **`NO-STOP`** on false-premise items (1–2 of 8) | **SEVERELY WEAKENED** | capped at 2.3 % of spec — a statement about our budget |
| `xhigh` **`NO-STOP`** on code review (0 content, 24,822 chars reasoning) | **SEVERELY WEAKENED** | same cause; ~7k tokens is nowhere near 262k |

**Both `NO-STOP` findings are retracted as model claims** and restated as: *at `n_predict`
6,144 — 2.3 % of spec — `xhigh` does not finish.* Whether it finishes at spec is **untested**.

## The finding this turns into, which is better

262,144 tokens of KV on this model is **16.0 GB at f16** — the entire 9070 XT, before weights.
At `turbo3_tcq` it is 3.2 GB, which fits but consumes a fifth of a 16 GB card for reasoning
alone.

**So the vendor's recommended `xhigh` envelope is unreachable on consumer hardware.** Locally
you are *always* running `xhigh` truncated, whether or not you know it. That is not a defect in
the model; it is a mismatch between how the setting is specified and what local deployment can
supply — and it is the strongest argument yet for `medium` as the local default, independent of
anything we measured about quality.

## Two more things the card settles

- **`presence_penalty` 0–2 is the documented mitigation for endless repetition.** We attributed
  greedy's non-termination to sampling and never tried the vendor's own remedy. `RETRACTION_NO_STOP`
  stands (recommended sampling did fix it) but the mechanism had a documented lever we missed.
- **YaRN to 1M is *static* in every open framework** — the scaling factor is constant regardless
  of input length, so it degrades short-context performance. Mark's instinct that extension is
  not equivalent to native training is what the card itself says.

## What would actually test termination

`.194` port 8081 runs at **131,072** context. An `xhigh` arm at `n_predict = 65,536` is **25 %**
of spec rather than 2.3 %, and is the smallest experiment that could support any termination
claim. ~84 min per item at 13 t/s — expensive, but one or two items settles it.
