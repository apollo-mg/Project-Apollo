# The MTP sidecar tensor-share bug has a silent variant — and it is benign where it is silent

**2026-09-03.** Context: `spiritbuun/buun-llama-cpp` issue **#118** (X1000QAQ) — combined loading of
a self-contained MTP drafter crashes with `GGML_ASSERT(ggml_can_mul_mat(a, b))`. Reporter's root
cause: `common/speculative.cpp:5616` calls `llama_model_share_tensors(model_dft, model_tgt)`
unconditionally for external-sidecar mode, overwriting the drafter's own `tok_embd`/`output`.

## Verified: the call is arch-agnostic

```cpp
// common/common.h
bool has_external_mtp_sidecar() const { return has_dft() && uses_mtp_as_primary_drafter(); }

// common/speculative.cpp:5611
if (external_mtp_sidecar) {
    // The loader borrows exact pointers so the compact file can be constructed.
    // Normalize them for the drafter scheduler now: same-device tensors stay
    // shared; foreign/meta tensors become draft-owned gathered copies.
    llama_model_share_tensors(model_dft, model_tgt);
}
```

No architecture check, no `nextn_shared_target_tensors` check. Any `-md X.gguf --spec-type
draft-mtp` takes this path. The comment shows the intent is pointer normalisation for **borrowed**
tensors; it is applied to every tensor, including ones the drafter shipped itself.

## The assert is the lucky case

| | issue #118 | this fleet |
|---|---|---|
| target | `Gemma4-12B` (`gemma4`), n_embd **3840** | `Qwen3.8-27B-Q6_K` (`qwen35`), n_embd **5120** |
| drafter | `mtp-gemma-4-12B-it` (`gemma4-assistant`), n_embd **1024** | `mtp-Qwen3.8-27B-Q4_0` (`qwen35`), n_embd **5120** |
| `nextn_shared_target_tensors` | absent | **absent** |
| own `token_embd` | yes, `[1024, 262144]` | yes, `[5120, 248320]` |
| outcome | **assert fires** (dim mismatch) | **no assert — silent substitution** |

Where drafter and target dims agree, `ggml_can_mul_mat` passes and the share succeeds. The drafter
then runs with a head it did not ship, with no error and no warning.

## But here the substitution is benign — arguably an upgrade

Dequantised and compared the two `token_embd.weight` tensors (64 sampled token rows):

```
drafter : Q3_K   target : Q6_K
NMSE    : 3.49e-02
cosine  : 0.983 (mean per row)
```

Cosine 0.983 in 5120 dimensions means **the same embedding at different precision** — a separately
trained head would be near-orthogonal. So this sidecar is derived from the target, and the share
swaps its Q3_K head for the target's Q6_K one.

## Why that matters for the fix

"Respect `nextn_shared_target_tensors`" is the obvious fix and it is not free: for derived sidecars
it would make the drafter keep its **lower-precision** head instead of borrowing the target's. That
is a silent, small quality regression landing on exactly the users who currently see no problem.

Suggested framing: guard on **dimension compatibility** for correctness (which fixes #118), and
treat the flag as intent rather than as a hard gate, since sharing an equivalent-but-higher-precision
tensor is beneficial. Whether that holds for sidecars that are *not* derived is untested here.

Also: this is why nobody caught it. Where the code is wrong it crashes loudly; where it is silent
it happens to help.

## Incidental

`mtp-Qwen3.8-27B-Q4_0.gguf` contains **Q3_K** tensors. The filename is not the spec — same family
of problem as [gguf-label-is-not-a-spec].

## Status

Diagnostics only, nothing posted. Not reproduced #118 directly (no gemma4 drafter with mismatched
dims on this fleet). Untested: whether acceptance rate differs with the share skipped — that needs
a patched build, and buun may be mid-fix.
