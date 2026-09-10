# A 1.7B draft for a 4B target is a 25% net LOSS — the ratio is wrong, and MTP is why

**Date:** 2026-09-07 · **Node:** desktop RX 9070 XT · **Engine:** `XHToken/llama.cpp` `4a3635c32`, gfx1201
**Target:** `Spark-X2.5-4B-Q4_K_M` 2.42 GiB · **Draft:** `Spark-X2.5-1.7B-Q4_K_M` 1.03 GiB
`-ngl 99 -c 8192 -np 1 -fa on`, fixed prompt, `max_tokens 600`, temp 0 · Raw: `.73`-less, `~/spec_ab.log`, `/tmp/spec_*.log`

Spark-X2.5 has no MTP head and none can be made. XHToken publishes a **1.7B sibling**, so
standard draft-model speculation is the nearest available substitute. This measures it.

## Result

| arm | decode | draft acceptance |
|---|---:|---|
| baseline | **108.91 t/s** | — |
| `--spec-type draft-simple --model-draft <1.7B> --spec-draft-n-max 4` | **81.98 t/s** | 0.591 (421/712), 0.485 (395/814); mean draft len 3.37, 2.94 |

**0.753× — a 25% slowdown.** Acceptance is fine at ~50–59%; the draft predicts well. The
problem is price: 1.7B against a 4B target is a **2.4:1** parameter ratio, so every drafted
token costs roughly 40% of a target token. Speculation only pays when the draft is close to
free relative to the target.

This is the quantitative case for MTP over a sibling draft. `qwen38-mtp` measured **1.68×**
(30.25 → 50.85 t/s) on Qwen3.8-27B because the MTP head is a single block (`blk.64`) sharing
the trunk — the draft is nearly free. A separate model, however small, is not.

## Flag trap — the first A/B was void and looked like a clean null

`--spec-type` defaults to **`none`**. Passing `--model-draft` alone loads the draft model and
logs:

```
common_speculative_init_result: loading draft model '.../Spark-X2.5-1.7B-Q4_K_M.gguf'
```

…and then does nothing. The first run measured **109.62 vs 109.72 t/s** — identical to three
significant figures — which reads exactly like "speculation is inert on this pair". It was
never enabled. The load message is not evidence that speculation ran; the **`draft acceptance`
line is**, and it is absent when `--spec-type` is unset.

Cross-ref `readiness-probes-lie`: a log line confirming a component *loaded* is not proof it is
*engaged*. The discriminator has to be a message that cannot appear unless the thing happened.

Also: `--draft-max` / `--draft-min` were **removed** upstream in favour of `--spec-draft-n-max`
/ `--spec-draft-n-min`. The old flags now hard-error with a message naming the replacement,
which is the good failure — but any script carrying them will refuse to start.

## Limits

One prompt, 2 generations per arm, one draft depth (`n-max 4`). No sweep over draft depth; a
shallower draft might reduce the loss but cannot make a 2.4:1 ratio profitable. `--spec-type`
also offers `draft-eagle3`, `draft-mtp`, `draft-dflash`, `draft-dspark` and several ngram
variants, none tested here.
