# `xhigh` does not improve calibration — it converts abstentions into non-termination

**2026-08-21.** RX 9070 XT (gfx1201), `Qwen3.8-27B-AD-IQ3_XXS`, buun `02f8581c6`, **f16 KV**,
`-c 16384 -np 1`, **greedy (`temperature=0`, `top_k=1`)**, 32.1 tok/s. `tier_cal` v0, 16 items in
8 matched pairs. Raw `sweep_rdna4_{low,medium,xhigh}_20260821.jsonl`.

**Controlled:** same model, same box, same items, same sampling. Only `reasoning_effort` varies —
which per `AFM-23` means only the injected system instruction varies.

## Result

| effort | injected instruction | confab | abstain | **NO-STOP** | answerable acc | over-abstain | **chars** |
|---|---|---|---|---|---|---|---|
| `low` | *"keep your thinking brief… move directly to the conclusion"* | 1/8 | 7/8 | **0/8** | 8/8 | 0/8 | 12,052 |
| `medium` | **none** | 1/8 | 7/8 | **0/8** | 8/8 | 0/8 | 13,069 |
| `xhigh` *(default)* | *"validate key assumptions, consider plausible alternatives…"* | 1/8 | 4/8 | **3/8** | 8/8 | 0/8 | **147,204** |

**`xhigh` is worse on the only axis that moved, and costs 11.3× `medium` to be worse.**

- **Answerable accuracy is 8/8 everywhere.** Effort does nothing for answering.
- **Confabulation is 1/8 everywhere, and it is the same item every time** — `CAL-U3`, Mendeleev's
  Nobel, answered `1906`, the year he was nominated and lost by one vote. Effort does nothing for
  confabulation.
- **The only thing effort changed is termination.** `CAL-U2`, `CAL-U6` and `CAL-U8` abstain
  correctly at `low` and `medium`; at `xhigh` they fail to emit an answer within 6,144 tokens
  *and* again within 12,288.

## Mechanism

The `xhigh` string instructs the model to *validate key assumptions and consider plausible
alternatives*. On a question whose premise is **false**, no assumption validates and no
alternative resolves — the instruction extends a search that has no terminating condition. It does
not change the conclusion: all three failures were flagged **recoverable**, meaning the reasoning
had already reached the answer and simply never emitted it.

Same mechanism drives the cost. Unanswerable-to-answerable ratio by effort:

| effort | ratio |
|---|---|
| `low` | 2.8× |
| `medium` | 3.4× |
| `xhigh` | **16.8×** |

**This substantially retracts `A5`.** *"Abstention items cost 4–9× their partners"* was measured at
`xhigh` and reported as a property of abstention items. It is largely a property of **`xhigh` on**
abstention items. A1's ~18.8 h sweep estimate was built on that ratio *and* the slower box; it is
off by roughly an order of magnitude.

## Deployment reading

If you want abstention behaviour from this model, **do not run `xhigh`** — and note that `xhigh`
is what you get by **sending nothing**. `medium` injects no instruction at all and matched `low`
on every outcome here at 8 % more tokens.

## What this does NOT support

- **n=1 per cell, 16 items.** A gate, not a measurement. No rate here may be quoted or differenced.
- **Greedy sampling.** The card recommends `temperature=1.0, top_p=0.95, top_k=20` for thinking
  mode, and greedy decoding on a reasoning model is a documented cause of exactly the `NO-STOP`
  signature. The three `xhigh` failures are therefore confounded, and the deciding arm
  (`CARD_CROSSCHECK.md`) has not run. **If recommended sampling removes `NO-STOP`, the only
  measured difference between effort levels disappears and this reduces to a cost result.**
- **One quant, one box.** `AFM-24`: the envelope is `n_ctx` 16,384 against a native 262,144 — 6 %.
  `NO-STOP` means *did not stop inside that envelope*, never *cannot stop*.

## One observation worth carrying to A1

On `.194`/Q6_K at `xhigh`, confabulation was also **1/8** — but the failing item was `CAL-U4`
(`30303`), not `CAL-U3`. **The rate was stable across quant and hardware while the identity of the
failing item changed.** For a paired design that is good news: McNemar draws power from
*discordant pairs*, and this hints discordance may run well above what the difference in rates
implies. It also means a comparison reported as a rate delta would have shown **zero** while the
items underneath disagreed.
