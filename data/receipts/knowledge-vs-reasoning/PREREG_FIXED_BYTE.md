# Pre-registration — at a fixed byte budget, is pruning a good way to spend it?

**Logged 2026-08-07, before any inference on any fixed-byte arm.** Arms selected by remote GGUF
header probe only. One arm (REAP-50 Q6_K) is already measured from
`RESULT_REAP_DOSE_RESPONSE.md` and is carried in unchanged — its number was known before this file
was written and is stated below rather than predicted.

## The question this leg exists to answer

Every REAP measurement in this campaign compares a pruned model to **its own unpruned parent**. That
answers "what does pruning cost?" but not the question a practitioner actually faces, which is:

> I have ~13 GB of VRAM. Should I spend it on more experts at fewer bits, or fewer experts at more
> bits?

Pruning has never been measured against its real alternative — **just quantizing harder**. If a
lightly-quantized heavily-pruned model loses to a heavily-quantized unpruned one at the same size,
REAP is not a useful compression strategy at this budget regardless of what it preserves.

## Design — bytes held constant, the allocation varied

| arm | experts | pruned | quant | size | vs 13.21 GB |
|---|---|---|---|---|---|
| **FB-BASE** | 64 | 0 % | Q3_K_S | 13.03 GB | −1.3 % |
| **FB-REAP09** | 58 | 9.4 % | Q3_K_M | 13.14 GB | −0.5 % |
| **FB-REAP19** | 52 | 18.8 % | Q3_K_L | 12.90 GB | −2.3 % |
| **FB-REAP39** | 39 | 39.1 % | Q5_K_S | 13.19 GB | −0.1 % |
| **FB-REAP50** | 32 | 50.0 % | Q6_K | 13.21 GB | 0.0 % *(already measured)* |

Max size spread **2.4 %**. Every arm is a **K-quant**, so no legacy-format confound. Verified by
header probe before download: `expert_count` 64/58/52/39/32, `expert_used_count = 4` on all five,
and **imatrix absent on all five** — so no fidelity asymmetry of the kind that voided the first Qwen
attempt.

**G-1 parity is deliberately relaxed on quant recipe**, because the quant tier *is* the traded
variable. What is held constant: bytes, base model, packager set, probe set, harness, host, and
imatrix status. This is a budget-allocation comparison, not a single-variable ablation, and is
labelled as such.

Same harness as the dose-response leg: `ikp_run.py` unmodified, 714 probes (T1 200, T2 200, T3 165,
T4 149) after `--exclude-source researcher`, K=1, temp 0, `--no-think`, `--max-tokens 160`,
`-c 4096 -ngl 99 -sm layer -np 1 --jinja --chat-template-file`, `.73` 2×P100 @ 1063 MHz / 150 W.
**G-1b applies** — the Akicou GGUFs carry no chat template, so the GLM template is forced on every
arm and asserted from the load log.

## Reference points already on the record

From `RESULT_REAP_DOSE_RESPONSE.md`, all at **Q6_K** (i.e. *not* byte-matched):

```
BASE Q6_K     24.61 GB   raw acc 68.9 %   refusal 11.2 %
REAP-09 Q6_K  22.48 GB   raw acc 52.5 %   refusal 22.1 %
REAP-50 Q6_K  13.21 GB   raw acc  1.8 %   refusal 96.9 %     <- carried in as FB-REAP50
```

## Predictions (§8)

| id | prediction | confidence |
|---|---|---|
| **P-F0** | **GATE** — FB-BASE (Q3_K_S) raw accuracy ≥ 30 %: 3-bit quantization does not destroy the model the way 50 % pruning does | 0.80 |
| **P-F1** | **HINGE** — FB-BASE beats FB-REAP50 by ≥ 30 pp raw accuracy at equal bytes | 0.85 |
| **P-F2** | Fixed-byte raw accuracy is **monotone decreasing** in prune ratio — spend bytes on experts, not bits | 0.65 |
| **P-F3** | Fixed-byte refusal rate rises monotonically with prune ratio | 0.70 |
| **P-F4** | **DOMINANCE** — FB-BASE (13.03 GB) beats REAP-09 **Q6_K** (22.48 GB, raw 52.5 %) despite being **42 % smaller** | 0.60 |

**P-F1 at 0.85 is not a real question** and is logged as a floor, not a discovery: FB-REAP50 already
sits at 1.8 %. Anything above 31.8 % clears it. It is here so that the headline comparison is scored
against a number fixed in advance rather than asserted afterward. Mark and I both expect the 3-bit
arm to bury it; that expectation is on the record with a date.

**P-F4 is the one that matters.** If an unpruned model at 3 bits beats a 9 %-pruned model at 6 bits
while also being 42 % smaller, REAP is **dominated on both axes at once** — worse accuracy *and*
bigger. That is a far stronger claim than "pruning costs knowledge", and it is the claim a
practitioner can act on. 0.60 is honest: Q3_K_S is aggressive, factual recall is known to be
quantization-sensitive, and 3 bits could plausibly fall below 52.5 % on its own.

**P-F2 at 0.65** allows for the possibility that the bit-depth penalty is steep enough at the
3-bit end to make a mildly-pruned 3.3-bit arm (FB-REAP09) beat the unpruned 3.0-bit one. If that
happens there *is* a sweet spot, and it would be the only pro-REAP result the campaign has produced.

## Interpretation, fixed before the data

- **P-F1 and P-F4 both hold** → at this budget REAP is not a rational choice; quantize instead. The
  campaign's practical recommendation becomes concrete and testable rather than a warning.
- **P-F2 fails with a peak at FB-REAP09 or FB-REAP19** → a genuine sweet spot exists, mild pruning
  plus moderate quantization beats either extreme, and REAP has a defensible niche. This is the
  outcome that would most change my view.
- **P-F0 fails** → 3-bit quantization is itself catastrophic for factual recall, the comparison has
  no valid low-bit end, and the finding becomes one about quantization rather than pruning.
- **P-F4 fails while P-F1 holds** → pruning is bad at extreme ratios but not dominated; the honest
  claim narrows to "don't prune past ~20 %".

## Limits, known in advance

- **K=1, temp 0**, not reproducible on this fleet. Existence proof, not rate.
- **Two variables move together by construction** (experts and bits). That is the point — the
  question is about a budget, not a mechanism — but no single-variable attribution is available
  from this leg.
- **One base model, one pruner, one packager pair.** Nothing here separates REAP-the-method from
  Akicou's application, and quantization behaviour is model-specific.
- **`committed n` will be reported with every cell** per the rule adopted in
  `RESULT_REAP_DOSE_RESPONSE.md`; raw accuracy is the headline wherever refusal exceeds ~50 %.
- **Closed-book only**, and **13.2 GB only** — a different budget could order the arms differently,
  and nothing here speaks to code or agentic ability, which is what REAP was calibrated to keep.
