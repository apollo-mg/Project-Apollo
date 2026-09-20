# Finding -- a score is meaningless without its instrument version, at every scale

**2026-09-19.** Three instances of the same error surfaced in one session, at three different
scales. Writing the rule down because the write-up will be tempted by all three.

## The rule

**A measurement is only comparable to another measurement taken on the same instrument, at the
same version, on the same configuration.** Where "instrument" means whatever actually produces
the number -- the machine, the build, the benchmark suite, the index revision.

## Instance 1 -- the machine (measured today)

Temp 0 at `-np 1` was proven deterministic on `.73`: **15/15 identical verdicts and identical
tool-call counts** across two passes, several matching to the second. That is strong evidence, and
I over-generalised it into "temp 0 is deterministic" rather than "temp 0 is deterministic on this
machine and config".

The replication arm caught it. Same model, same frozen seed `806c5016`, same scenario, temp 0:

| | `rent-amount` |
|---|---|
| `.73`, 2 GPUs, incremental prism build | **SUSPECT** (zero tool calls) |
| `.194`, 4 GPUs, fresh prism build | **CORRECT** |

Different device count means a different layer split and a different floating-point reduction
order; the builds are separate compilations. Either suffices. **Determinism is a property of a
machine-and-config, not of the sampling setting.**

**Cost of not knowing this:** a cross-machine comparison had already been drawn and stated as a
finding ("the anchor beats every quantized arm on the look-before-you-answer item") before the
control invalidated it.

## Instance 2 -- the build (controlled for, in the fidelity ladder)

The same concern drove Amendment 1 of `PREREG_CODEC_LADDER.md`: the Bonsai cells ran on the prism
fork while the stock cells ran on buun, so `C-XBIN` re-scored one model on both binaries. They
agreed to **3.1e-5**, so that comparison was valid. It was not assumed to be.

## Instance 3 -- the benchmark index (external)

Artificial Analysis Intelligence Index **v4.3.2** incorporates a named set of 10 evaluations
(AA-Briefcase v1.1, GDPval-AA v2.1, AutomationBench-AA, Terminal-Bench 4.0, SciCode, Humanity's
Last Exam, GDP.pdf, CritPt, AA-Omniscience, AA-LCR v1.1). Earlier index versions incorporated a
different set.

On v4.3.2 Qwen3.8-27B scores **34** against a frontier of 50-53. Mark's recollection is that at
release it sat within ~10 points of the top. **Both can be true with the model unchanged**, because
the index was revised between those observations.

**So: compare models WITHIN an index version. Never compare a score across versions to infer that
a model improved or regressed.** That is the same error as comparing our `.73` and `.194` runs.

## Applied to this project's own numbers

Anything published from today must carry:

- **which node** (`.73` 2x P100 vs `.194` 4x P100),
- **which binary and commit** (`buun-sm60-qual 9ae8f0f4` vs `prism 9a9394a8`),
- **which seed** (`806c5016`, rebased +28d),
- **which reasoning effort** (`medium` -- *not* the `high`/xhigh that AA's published figure uses),
- **and which scenario pool** (`scenarios_v1_pool_gate.json`, 15 items).

The fidelity ladder already does this. The agentic panel must too, and the cross-machine gate data
must **not** be mixed into the panel's four-arm comparison.

## The asymmetry worth remembering

Proving determinism is cheap and feels conclusive. **Proving it TRANSFERS is a separate experiment**
and costs a full arm. It is worth it: this one cost ~40 minutes and prevented a wrong finding from
reaching a receipt.
