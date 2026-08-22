# Claim inventory — reasoning_effort writeup

**2026-08-22.** Fact-check sheet, not prose. Every row is either safe to assert, safe with a
stated caveat, or must not be said. Mark writes the post.

## SAFE — measured, reproducible, receipts on disk

| claim | evidence | receipt |
|---|---|---|
| `reasoning_effort` is consumed by the **chat template**, which prepends text to the system message. It is not a sampling parameter | template pulled from `/props`, rendered with jinja2, only the kwarg varied | `RESULT_EFFORT_IS_A_PROMPT_EDIT.md` |
| **Default is `xhigh`** — sending nothing gives you a 237-char injected instruction | `reasoning_effort\|default('xhigh')` | same |
| **`high` is silently rewritten to `xhigh`** | template alias branch; renders byte-identical | same |
| **`medium` injects nothing** — there is no `medium` branch; it validates then falls through | template has `if xhigh` / `elif low` only | same |
| **`enable_thinking=False` works differently** — pre-fills an empty `<think></think>` in the generation prompt rather than injecting instruction | rendered comparison | this session |
| **The declaration sentence carries the effect, not the length** — 33 chars `"Reasoning effort is set to xhigh."` → **3.65×** output; 214 chars of filler with no declaration → **1.03×** | ablation round 2, 12 cells/condition | `ablation2_results.jsonl` |
| **Direction is parsed** — same filler with the declaration reading `low` stays at baseline (1.02×) | ablation round 2 | same |
| **`xhigh` cost 5.85× `medium`** on the calibration tier, identical items | 3 seeds each, card sampling | `RESULT_EFFORT_SWEEP.md` + `card_*.jsonl` |
| **No accuracy benefit found** — 8/8 answerable at both efforts across 6 passes; 24/24 on novel hard items at both | tier_cal + hard probe v2 | `RESULT_EFFORT_SWEEP.md`, `hard2_results.jsonl` |
| **`medium` is seed-stable, `xhigh` is not** — 16/16 identical verdicts across 3 seeds vs 3 items flipping | card-sampling run | `card_medium_rep*.jsonl` |
| **262,144 tokens of KV = 16.0 GB at f16** on this model, so the vendor's recommended reasoning budget does not fit a 16 GB card | arithmetic from measured 65,536 B/token | `CORRECTION_BUDGET_VS_SPEC.md` |

## SAFE ONLY WITH THE CAVEAT ATTACHED

| claim | required caveat |
|---|---|
| `xhigh` degrades calibration (abstention 7/8 → 3–6/8, confabulation up to 3/8) | **16 items, 3 seeds. A gate, not a measurement.** The ablation could not reproduce it at 12 cells/condition — cost replicates, calibration does not yet |
| "`medium` is the better local default" | rests on cost + stability + the KV arithmetic. It does **not** rest on a measured quality win, because none was found in either direction |

## DO NOT SAY — retracted internally

| retracted claim | why |
|---|---|
| *"`xhigh` causes non-termination"* | measured at `n_predict` 6,144 = **2.3 %** of the vendor-specified 262,144 reasoning budget. Restated: at 2.3 % of spec it does not finish. Whether it finishes at spec is **untested** |
| *"longer system prompts cause more reasoning"* | round 1 confounded length with the declaration — my own "neutral" control contained the treatment verbatim. Round 2 kills it: 214 chars without the declaration = 1.03× |
| *"greedy decoding causes the model to hang"* | true as measured, but the card documents `presence_penalty` 0–2 as the remedy and we never tried it. State the finding, not the diagnosis |
| any per-item calibration **rate** | 8 items per arm. Wilson 95 % on 2/8 is [7 %, 59 %] |

## Numbers to double-check before publishing

- 237 vs 207: **237** = full rendered system block; **207** = the injected string alone. I used
  both loosely in conversation. Pick one and define it.
- 5.85× is `.194`/Q6_K/card sampling. The RDNA4/IQ3_XXS/greedy figure was **11.26×** — different
  box, quant *and* sampling. Do not mix them.
- Everything is **one model, one architecture**. `gpt-oss-20b` is downloaded and unrun.

## Structural notes (audience: r/LocalLLaMA)

- The two posts that landed there both led with a **concrete, checkable, surprising fact** and a
  fix — 295 pts / 201K views, 61 pts / 80K. This one has the same shape: *"the default setting
  costs you 5.85× and buys nothing measurable, and it's just a sentence in the prompt."*
- The strongest hook is arguably the **VRAM arithmetic**, because it is unarguable and everyone
  can check it: the recommended `xhigh` budget does not fit on the card most readers own.
- Reproduction instructions matter more than the numbers here — anyone can render the template
  and diff it in five minutes, which is the same "three lines fix it" energy as the P100 post.
- The ablation is the part nobody else has: **33 characters, 3.65×, and the direction is parsed.**
