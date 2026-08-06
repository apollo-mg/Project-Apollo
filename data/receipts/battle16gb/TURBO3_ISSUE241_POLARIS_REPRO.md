# REPRODUCED: turboquant#241 turbo3 V-cache corruption is real, and it is Polaris-specific

Bench rig `.76`, **AMD RX 580 8 GB (Polaris10, GCN4)**, Vulkan/**RADV**, CachyOS live USB.
Engine `llama-cpp-turboquant` **9971 (`c26cbdffc`)**, self-built x86-64-v2 Vulkan.
Date 2026-07-30. Issue: [TheTom/llama-cpp-turboquant#241](https://github.com/TheTom/llama-cpp-turboquant/issues/241) (suhermanme).

Supersedes the negative result in `TURBO3_ISSUE241.md`, which tested RDNA4 only and explicitly
named RADV-on-Polaris as **candidate #1**. That candidate is now confirmed.

## Result: turbo3 on the V cache corrupts context. Deterministically.

`Crow-9B` (Qwen3.5, IQ4_XS), `-c 16384 -b 1024 -ub 512 -fa on -np 1 -ngl 99 --cache-ram 0`,
their exact prompt ("Write a 500-word essay about Linux."), temp 0, `cache_prompt:false`.

| K / V | gzip ratio | chars | verdict |
|---|---|---|---|
| f16 / f16 | **0.5097** | 1903 | correct (control) |
| turbo4 / turbo4 | **0.5024** | 1871 | correct |
| turbo4 / turbo2 | **0.5021** | 1944 | correct |
| **turbo4 / turbo3** | **0.2736** | 1962 | **CORRUPT** ← their reported pair |
| **turbo3 / turbo3** | **0.3474** | 2344 | **CORRUPT** |
| **f16 / turbo3** | **0.1753** | 2202 | **CORRUPT** (degenerate repetition) |

The three cells **without** turbo3 cluster at **0.5021–0.5097** and emit near-identical correct
reasoning. Every cell **with** turbo3 on V falls to **0.1753–0.3474**. Clean separation, no overlap.

### Run twice, byte-identical

Two independent runs, fresh server process per cell, 12 server loads total:

```
cell               run1               run2               identical
kturbo4_vturbo3    173da68272ccfbe3   173da68272ccfbe3   YES
kf16_vf16          ad9dd4fa776fefde   ad9dd4fa776fefde   YES
kturbo4_vturbo4    9e33a09474a1b8f0   9e33a09474a1b8f0   YES
kturbo4_vturbo2    0b3b5c4235d56814   0b3b5c4235d56814   YES
kturbo3_vturbo3    65e01d083c834498   65e01d083c834498   YES
kf16_vturbo3       b539962f600d0bcb   b539962f600d0bcb   YES
```

**This is a deterministic reproduction** — Tom can expect the same bytes, not just the same
symptom. (`cache_prompt:false`, no `-cb`: the deterministic regime established today in
`MTP_CACHEPROMPT_FALSIFICATION.md`.)

## The failure modes — read them literally

**Control (f16/f16, turbo4/turbo4, turbo4/turbo2)** — the model reads its prompt correctly:

> `1. **Analyze the Request:** * **Topic:** Linux. * **Format:** Essay. * **Length:** Approximately 500 words.`

**turbo4 / turbo3** (their exact pair) — invents a persona that appears nowhere in the prompt:

> *"The user wants an essay about Linux written in the style of a specific persona. The persona
> is a "tall, lanky guy in his late teens" who's "scrawny as a rail" and "looks like a model of
> the 1950s.""*

**turbo3 / turbo3** — cannot see the prompt at all:

> *"The user wants an essay-style analysis of a specific text, but the prompt is just a single
> word: "SS". … often associated with illicit activities."*

**f16 / turbo3** — degenerate repetition:

> *"The essay below is about the impact of open-source software on the tech industry. It is
> written in an essay format and is about 500 words long. *** The essay below is about the impact
> of open-source software on the tech industry. It is written in essay format…"*

That last one is **the same failure class the reporter saw** — degenerate looping. English rather
than `。，。，。，` because this is a different model with a different vocabulary; the structure is
identical.

## Two things this pins down that a single data point could not

**1. It is the V side, specifically.** `f16` K with `turbo3` V still fails — and fails *worst*
(0.1753). K-cache compression is irrelevant to the bug. This matches the issue title.

**2. It is Polaris, not the codec and not Vulkan.** Same commit `c26cbdffc`, same six cells:

| hardware | backend | result |
|---|---|---|
| RX 9070 XT (RDNA4/gfx1201) | HIP/ROCm | 6/6 healthy |
| RX 9070 XT (RDNA4/gfx1201) | Vulkan/RADV | 6/6 healthy |
| **RX 580 (Polaris10/GCN4)** | **Vulkan/RADV** | **3/3 turbo3 cells CORRUPT** |

The RDNA4 Vulkan arm is what makes this decisive: **RADV itself is fine on RDNA4**, so this is
not "the Vulkan turbo3 path is broken." It is Polaris/GCN4 specifically.

**Non-monotonicity is the clincher.** turbo2 (more compressed) works, turbo4 (less compressed)
works, turbo3 in between is broken. A genuine precision/quality tradeoff would degrade
monotonically. A hole in the middle of the ladder is a bug — and it is exactly the pattern the
reporter described (f16 OK, turbo2 OK, turbo4 OK, turbo3 corrupt).

## Deltas from the reporter's setup — state these

| | them | us |
|---|---|---|
| GPU | RX 580, Polaris/GCN4 | **same class** |
| backend | Vulkan/RADV | **same** |
| model | Qwen3.6-35B-A3B **Q4_K_M** (MoE) | Crow-9B (Qwen3.5, IQ4_XS, dense) |
| context | 256,000 | 16,384 |
| MoE offload | `--n-cpu-moe 36` | none, fully GPU-resident |
| build | 9953 (`30d6881eb`) prebuilt | 9971 (`c26cbdffc`) self-built |

Their model cannot be loaded on this box (7 GB RAM). Crow-9B was chosen for Qwen lineage and a
multilingual vocabulary — a model without CJK punctuation could not have produced their exact
signature even if the bug were present.

**The deltas now cut in the useful direction:** the bug reproduces *despite* a different model,
1/16th the context, no CPU offload, and a build 18 commits newer. It is not depth-dependent, not
MoE-dependent, and **not already fixed**.

## Methodological correction: the gzip gate under-detected

My gate (`ratio < 0.15` = degenerate) was calibrated on the CJK-punctuation loop and called
**five of six cells "healthy"**, including two that are plainly corrupt. Absolute thresholds are
the wrong instrument for a different model.

**The right gate is relative:** compare each cell's ratio to the **f16/f16 control on the same
model**. Here the controls sit at 0.50 and every corrupt cell is ≤ 0.35 — a 1.4× to 2.9× gap with
no overlap. Had I trusted the absolute threshold and not read the outputs, I would have filed a
second false negative. Fix the gate before reusing these scripts.

## Provenance

- `/mnt/usb/turbo3_polaris.sh` (bench rig); local copy `scratchpad/turbo3_polaris.sh`
- `/mnt/usb/turbo3_polaris_run1/` and `/mnt/usb/turbo3_polaris/` — 12 responses, 12 server logs
- Binaries: `engines/llama_cpp_turboquant/build_vk_v2/` (Vulkan, `GGML_NATIVE=OFF`, AVX/AVX2/FMA/
  F16C off, `-march=x86-64-v2`), `.note.gnu.property` stripped from executables — the G3258 is
  x86-64-v2 and CachyOS marks all executables v3-needed via its startup objects
- Prior negative: `TURBO3_ISSUE241.md` (RDNA4, both backends)
