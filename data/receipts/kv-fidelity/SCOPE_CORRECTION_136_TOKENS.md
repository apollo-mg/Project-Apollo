# Scope correction: the whole kv-fidelity line was measured with a 136-token KV cache

**2026-08-18.** Applies to **`RESULT_U5_FIDELITY.md` (U5)**, **`RESULT_U5B_BUUN.md` (U5b)**
and **U5c, currently running**. Found by reading `frontier-hazard.cpp` while answering a
question about multi-turn outcomes — not by a failed run.

## What the instrument actually does

```c
cp.n_ctx  = n_prefix + 8;                            // line 116
if ((int) toks.size() > n_prefix) toks.resize(n_prefix);  // line 167 — prompts TRUNCATED
const int band = band_of(t);                         // line 321, t ranges 1 .. npos-2
static const int BAND_EDGES[] = {0, 128, 512, 2048, 8192, 1 << 30};
```

Every panel ran `--n-prefix 128`. Therefore:

- **The KV cache under test is 136 tokens.** `n_ctx = n_prefix + 8`. There is no `-c`
  override in this tool; context is *defined* by `--n-prefix`.
- **Prompts are truncated to 128 tokens.** The 1203+ character wikitext prompts were
  selected for length and then cut to 128 tokens regardless.
- **All scored positions are < 128, so every token lands in DEPTH band 0.** The instrument
  carries five bands reaching past 8192. **We have only ever populated the shallowest one.**
  U5c's per-arm `DEPTH` output will contain four empty rows; that is expected, not a bug.

## Why this matters

KV-cache quantization error is the one thing you would expect to **grow with depth** — more
accumulated quantization noise, and attention distributed over a longer quantized history.
**A 136-token cache is the best case for any codec.**

So every number in this line — turbo2's R 362, turbo4's 32.2, turbo3_tcq's 63.2, the
turbo8-vs-`q8_0` comparison — is a **shallow-context** measurement. They remain valid *as
such*, and the within-panel rankings stand, but **none of them licenses a claim about
behaviour at realistic context lengths**, which is where these codecs are actually deployed
and where they are actually sold.

Stated plainly: **we have been measuring KV-cache fidelity with essentially no KV cache.**

## What does NOT fill the gap

`scripts/experiments/receipt_depth_ladder_tom_*.json` runs to 100k context, but measures
needle `recall_rate`, and **every arm returns 1.000 — including `tom_100k_turbo4` at
ctx 1000**, where there is barely a cache to quantize. An instrument returning a perfect
score for its near-trivial control is at its ceiling. Rule of three on 48 probes puts the
smallest detectable failure rate at ~6 %. **It cannot resolve the question and must not be
quoted as depth evidence for or against any codec.**

## What answering it would take

Raising `--n-prefix` populates the bands directly — the tool was built for this and we ran
it in its degenerate configuration. Two real constraints before quoting a cost:

1. **Two contexts, not one.** frontier-hazard builds an f16 reference *and* the quantized
   context. At the ~68 KiB/token measured for Qwen3.8-27B, 8192 tokens is ~557 MiB per
   context; 32k is ~2.2 GB for the f16 reference alone. Needs checking against the 27B Q6_K
   resident on the P100s before promising a runtime.
2. **The prompt file has to be rebuilt.** Current wikitext prompts are ~300 tokens, so
   anything past `n_prefix ≈ 256` needs concatenated documents — and **concatenation changes
   what is being measured.** Cross-document context is not the same instrument as
   within-document context, and a depth ladder that silently swaps instruments mid-sweep
   would be a worse error than the one this file corrects.

## Correction discipline

This is a scope error, not a measurement error: nothing published needs retracting, but
every claim in the line needs the qualifier *"at 128-token context"* attached, and the
receipts above should be read with this file. Logged because the campaign has been quoting
these R values in cross-codec comparisons for two days without the qualifier.
