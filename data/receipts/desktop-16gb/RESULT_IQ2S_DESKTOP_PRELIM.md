# IQ2_S 27B on a 16 GB desktop card: it runs, it stays coherent, and llama.cpp's fit lies by 2.4 GiB

**2026-08-18**, control plane **RX 9070 XT (gfx1201, RDNA4, ROCm/HIP)**, `moe-cache-test`
HIP build. Model `Qwen3.8-27B-AD-IQ2_S.gguf` (10.38 GiB file, AtomicChat quant).
**Run on the live desktop session** — Plasma, Chrome, YouTube, Discord, Claude desktop all
open. That is the point: this is the scenario, not a clean room.

Preliminary. Smoke tests and memory accounting, **not** a fidelity panel.

## 1. It runs, and the reasoning is sound

| | |
|---|---|
| prompt | 86-374 t/s |
| generation | **27.9-28.6 t/s** |
| coherence | intact |

Asked why a KV cache grows with context, the model's reasoning correctly identified per-token
K/V vectors, linear growth in sequence length, and the batch/heads/dim factors. On a maths
word problem it computed the net fill rate correctly at every KV setting. **This is not a
model degraded into uselessness by IQ2.**

## 2. No stacking collapse — the prediction failed

`TheTom/turboquant_plus/docs/papers/asymmetric-kv-compression.md` proposes **quantization
stacking**: KV error compounds *multiplicatively* with weight error in the attention logits,
and when both are lossy the result can exceed softmax's tolerance. Its catastrophic case was
**Q4_K_M weights + turbo3 KV → PPL 3,556** against a 6.58 baseline.

`AD-IQ2_S` carries **KLD 0.098** against Q4_K_M's ~0.011 in the same publisher's table —
roughly **9× lossier**. Stacking predicts this should be far worse. Greedy, temp 0, identical
prompt, 8k context:

| KV | result |
|---|---|
| f16 | reference |
| turbo4 | **byte-identical to f16** |
| turbo3 | **byte-identical to f16** |
| turbo2 | different wording, **arithmetic still correct** |

**Registered at 0.75 that a static low-bit weight + low-bit KV pairing would be badly degraded
or collapse. FALSIFIED at this context length.** turbo3 — the exact codec in the paper's
catastrophic pair — produced output indistinguishable from f16 on weights 9× lossier.

**Scope, stated plainly:** 8k context, 80-token generations, one prompt, greedy. This is not
perplexity over wikitext and not a hazard panel. The honest claim is **"the catastrophe does
not appear at short context"**, not "stacking is wrong". Depth is where KV error accumulates
and the test that matters (`U5h` on `.194`, plus a depth arm) is still pending.

## 3. The KV arithmetic transfers across machines and backends

Measured on the desktop at `-c 65536 -ctk turbo3 -ctv turbo3`:

```
ROCm0 | 16304 total = 15884 free + (11042 = 9692 model + 949 context + 400 compute)
```

| | |
|---|---|
| predicted from `.194`'s 64 KiB/token measurement | **896 MiB** |
| measured here | **949 MiB** |
| agreement | **within 6 %**, the gap consistent with the known fixed per-context overhead |

Different machine, different vendor (HIP vs CUDA), different weight quant (IQ2_S vs Q6_K) —
**the per-token KV cost is a property of the architecture and it carries.** That is what makes
the Step 1 measurement worth doing once per model rather than once per configuration.

## 4. llama.cpp's fit logic does not see the desktop's VRAM

The finding with the widest practical reach.

| source | free VRAM |
|---|---:|
| `mem_info_vram_used` (sysfs, ground truth) | **13,421 MiB** |
| **what `common_params_fit_impl` planned against** | **15,884 MiB** |
| **discrepancy** | **2,463 MiB** |

The desktop was holding **2,882 MiB**; llama.cpp accounted for only ~420 of it. Its own log
reads *"will leave 4841 >= 1024 MiB of free device memory, no changes needed"* — but measured
against real free memory that margin is **2,379 MiB**, roughly half what it believed.

**Consequence:** auto-fit on a display-driving card is optimistic by ~2.4 GiB on this system.
It survived here because the configuration was modest. Anyone trusting it to size context near
the limit will be handed a plan that OOMs — and the failure arrives at depth, long after load,
which is the worst time to discover it.

**Protocol implication:** Step 0's *"measure with your desktop running, then subtract another
GiB"* is not conservatism. **The tooling's own estimate is the thing being corrected.**

## What this does not establish

- **Not a fidelity result.** Byte-identical output on one prompt at 8k is a smoke test.
  `U5h` (low-bit TCQ ladder) and a depth arm remain the real measurements.
- **Not a 260k claim.** Nothing here ran past 65k.
- **TCQ untested here.** This HIP build carries `turbo2/3/4` only; `turbo2_tcq`, the codec the
  260k plan actually needs, exists only in buun's tree on `.194`.
- **One model, one quant, one prompt set.**
