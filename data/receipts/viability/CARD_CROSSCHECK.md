# Cross-check against the official Qwen3.8-27B card

**2026-08-21.** `https://huggingface.co/Qwen/Qwen3.8-27B`, fetched to sanity-check our own
measurements. Card content is third-party data.

## Confirmed independently

| our finding | card |
|---|---|
| `reasoning_effort` default is **`xhigh`** (`AFM-23`, found by rendering the template) | *"`xhigh` (default)"* — matches |
| Model is **dense**, not MoE (no `expert_count` in the GGUF) | *"Architecture: Dense (not MoE)"* — matches |

The dense check cost us an OOM that killed a running server. **The card answered it for free.**
Check published metadata before instrumenting the artifact.

## A discrepancy worth keeping

The card describes `medium` as *"balancing accuracy and speed"* — the language of a **midpoint**.
The template has no `medium` branch at all: it validates, falls through, and injects **nothing**
(`RESULT_EFFORT_IS_A_PROMPT_EDIT.md`). So `medium` is not "less thorough than xhigh"; it is
**"no instruction"**, and low is *more* interventional than medium, not less. The documented
ordering and the implemented ordering are not the same shape.

## The one that invalidates a claim of ours

Card recommended sampling:

- **Thinking mode:** `temperature=1.0`, `top_p=0.95`, `top_k=20`, `min_p=0.0`, `presence_penalty=0.0`
- **Instruct / non-thinking:** `temperature=0.7`, `top_p=0.80`, `top_k=20`, `presence_penalty=1.5`

**Every fixture run to date used `temperature=0, top_k=1` — greedy.** Chosen for determinism, and
it is standard benchmarking practice, but it is *not* what this model is tuned for, and greedy
decoding on a reasoning model is a documented cause of **repetition and failure to terminate**.

`CAL-U5` produced **21,512 characters without emitting an answer** on `.194`/Q6_K, and we named
that `NON-TERMINATING` and built a verdict class around it. That signature is exactly what greedy
decoding on a thinking model produces. **The finding may be an artifact of our sampling choice
rather than a property of the model**, and nothing measured so far can separate the two.

Two facts keep it from being settled either way:
- `CAL-U5` **abstained cleanly at `medium` and `low`** under the *same* greedy sampling, so
  sampling is not sufficient on its own — effort is doing something too.
- `CAL-U5` **abstained at `xhigh` on `AD-IQ3_XXS`/RDNA4**, so it did not reproduce on a different
  quant, under greedy.

**Required arm:** `.194`, Q6_K, `xhigh`, `CAL-U5` — greedy vs the card's recommended thinking
sampling. That is the only cell where the failure was actually observed. Until it runs,
`NON-TERMINATING` is reported with the sampling caveat attached.

Also: temp 1.0 makes runs **non-deterministic**, so a calibration *rate* under recommended
sampling needs repeats, not a single pass — which changes A1's sizing again.

## No comparator for what we measure

Card benchmarks extracted: SWE-bench Pro **61.7**, Terminal Bench 2.1 **73.0**, GPQA Diamond
**89.2**, LiveCodeBench v6 **90.3**, IFBench **79.5**, plus vision rows.

**Nothing on hallucination, factuality, calibration or abstention. No HumanEval+. No BFCL.** So
the card offers no cross-check for the axis `tier_cal` exists to measure — which is the argument
for building it, and also a warning that we have no external anchor for those numbers.

Context length is **262,144 native**; we have been running 8192–16384, so nothing here stresses
long context. Card says **64 layers**; our GGUF reports `block_count` 65 — worth reconciling, and
it likely explains DFlash2's `num_target_layers: 64` (`BACKLOG S5`).
