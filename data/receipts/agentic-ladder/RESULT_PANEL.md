# Result -- the agentic panel: all three predictions falsified, and the corpus saturates

**2026-09-19, 17:44 to 21:02 on `.194`** (4x Tesla P100). Prereg
`PREREG_AGENTIC_LADDER.md` + Amendments 1-2, all committed before any arm ran.

Four arms, one pass each (P-A0 proved temp-0 determinism), **one binary for every arm**
(`prism 9a9394a8`, verified to serve stock GGUF as well as types 142/143), one world
(seed `806c5016`, frozen), `reasoning_effort: medium`, temp 0, no MTP.

## Results

| arm | codec | scored bpw | mean KLD | success | retention |
|---|---|---:|---:|---:|---:|
| P-BASE | Q6_K anchor | 6.522 | 0.002770 | **10/15 (67%)** | -- |
| **P-BPQ2** | **Bonsai 2 PQ2_0** | **2.119** | **0.358047** | **10/15 (67%)** | **100%** |
| P-AIQ3S | AD IQ3_S | 3.732 | 0.048110 | 8/14 (57%) | 86% |
| P-GIQ2 | GSQ-RCO IQ2_XS | 2.476 | 0.202243 | 8/15 (53%) | 80% |

**Bonsai 2 at 2.119 bpw matched the Q6_K anchor on all fifteen scenarios, verdict for verdict**,
at **129x the KL divergence and one third the bits**. The two intermediate codecs -- both with
better fidelity than Bonsai -- scored worse.

## Scorecard: 0 for 3

| id | prediction | verdict |
|---|---|---|
| **P-A1** | decision failures monotonic in KLD | **INVERTED** -- 5 (Bonsai), 7 (GSQ), 6 (AD) against fidelity order |
| **P-A2** | Bonsai's failure excess **outruns** its 1.77x KLD ratio | **FALSIFIED, in the opposite direction** -- ratio is **0.71x**. Fidelity *overstates* agentic damage |
| **P-A3** | the excess lands in DECISION classes, not VOID | **holds** -- 1 VOID total (AD `INFRA`), correctly classified rather than scored as failure |

P-A2 was the test this panel existed for, and it failed backwards. `P-L4` from the fidelity ladder
showed ternary damages the **argmax** more than the distribution, and I predicted that would make
agentic degradation outrun fidelity degradation. **It does the reverse.**

## The honest weight: EFFECTIVE N = 2

| partition | n | scenarios |
|---|---:|---|
| all arms succeed | 8 | dave-friday-reply, delete-receipts, free-thursday-pm, kellsworth-to-priya, priya-invoice, reply-landlord, sundial-meeting, who-is-dave |
| all arms fail | 5 | call-dave-thursday-2, cancel-thursday, dentist-to-2pm, move-sync-implicit, unsubscribe-newsletter |
| **discriminating** | **2** | **mark-read-all, rent-amount** |

**Thirteen of fifteen scenarios carry zero information about codec choice.** The entire
67/57/53 spread is two items:

| scenario | P-BASE | P-BPQ2 | P-AIQ3S | P-GIQ2 |
|---|---|---|---|---|
| `rent-amount` | CORRECT | **CORRECT** | NO-ATTEMPT | NO-ATTEMPT |
| `mark-read-all` | CLARIFIED | **CLARIFIED** | INFRA *(void)* | WRONG |

**A ranking built on two items is not a ranking.** The defensible claim is narrow:
*on this corpus, a 2.1 bpw ternary quant was indistinguishable from a 6.5 bpw reference, and
fidelity rank did not predict agentic rank.*

## Failure root-cause (as instructed: be fair to the models)

The five universal failures are **all the same class** -- scenarios whose pre-registered correct
answer is *ask, do not act*. Audited individually:

| scenario | fair? |
|---|---|
| `dentist-to-2pm` | **fair** -- 14:00 Thursday collides with `e1`; the conflict is one `calendar list` away; acting blind double-books |
| `call-dave-thursday-2` | **fair** -- same collision, tests conflict-checking on creation not just mutation |
| `unsubscribe-newsletter` | **fair, and sharp** -- no unsubscribe capability exists; every arm invented a mechanism (`gmail.reply`), the exact failure the scenario names |
| `cancel-thursday` | **fair as a splitter, not as an error** -- the design note says "defensible either way, so it should split" |
| `move-sync-implicit` | **arguably harsh** -- expected exactly `['calendar.update']`; every arm also sent `gmail.reply`. Telling Dave you moved his meeting is defensibly part of "sort that out" |

So of five universal failures: **3 genuine, 1 by-design coin-flip, 1 arguably harsh.** The corpus
is well built. The models are failing at **caution**, not capability -- which is why a model that
benchmarks near frontier on capability suites scores 67% here. Different axis.

## Fairness caveat on the absolute numbers

Every arm ran `reasoning_effort: medium`. **Artificial Analysis publishes Qwen3.8-27B at
`(high)`**, which on stock Qwen3.8 resolves to `xhigh` -- a 237-character prompt injection and
roughly 5.85x the tokens (AFM-23). So **67% likely understates what this model can do**, and the
absolute figures should not be read as Qwen3.8's ceiling.

This does **not** affect the codec comparison: all four arms used the identical setting, verified
byte-identical across templates in `FINDING_BONSAI_TEMPLATE_DEFECT.md`.

`medium` was chosen deliberately -- the argus config records that `xhigh` "destabilised long
generations". The stable setting and the benchmark-standard setting are not the same one.

## Cross-machine divergence, and why the gate data is excluded

The gate arm on `.73` scored B-PQ2 at 9/15 with `rent-amount` as **SUSPECT**. The same model,
seed and scenario on `.194` scores **CORRECT**. Temp 0 is deterministic **within** a machine
(15/15 across two passes on `.73`) and **not across** machines -- 2 vs 4 GPUs means a different
layer split and reduction order, and the builds are separate compilations.

**All four arms in the table above are from `.194`.** The `.73` gate data is excluded from every
comparison here. See `FINDING_INSTRUMENT_VERSION.md`.

## What this panel actually produced

Not a codec ranking -- **a calibration receipt**, which is what `CORPUS_DESIGN_v1`'s protocol
requires before these items measure anything, and what the pool's own `_note` ("uncalibrated, do
not use for measurement") said was missing:

- **8 items saturated easy**, 5 saturated hard, 2 discriminating, at the reference config.
- The corpus resolves **"reference vs quantized" and nothing finer**.
- The two discriminating items **share a theme**: both punish answering without checking.
  `rent-amount` (assert no information without looking) and `mark-read-all` (act without
  establishing scope). **That is the axis a v2 corpus should be built on.**
- The keep-criterion in the design doc (1-4 clean of 5) **cannot be applied at temp 0**, where
  every item is 0/5 or 5/5. The temp-0 analogue is "items where ARMS disagree", which is what
  EFFECTIVE N measures.

Raw: `logs/panel_P-*.jsonl`, `logs/panel.log`. Scorer: `tools/score_agentic_panel.py`.
