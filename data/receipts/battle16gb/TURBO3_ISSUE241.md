# turboquant#241 — turbo3 V-cache corruption does NOT reproduce on RDNA4, HIP or Vulkan

Control plane, RX 9070 XT (gfx1201). Date 2026-07-30.
Issue: [TheTom/llama-cpp-turboquant#241](https://github.com/TheTom/llama-cpp-turboquant/issues/241)
filed by **suhermanme**: *"turbo3 V-cache produces corrupted output, turbo2 and turbo4 are correct."*

## Their report

| | |
|---|---|
| card | **AMD RX 580** (Polaris) |
| backend | **Vulkan / RADV** |
| build | turboquant **9953 (`30d6881eb`)** prebuilt, GCC 11.4.0 |
| model | `bartowski/Qwen_Qwen3.6-35B-A3B-GGUF` **Q4_K_M** |
| serving | `-ctk turbo4 -ctv turbo3 -c 256000 --n-cpu-moe 36 -ngl 99 --mlock -fa on` |
| result | f16 OK · turbo2 OK · **turbo3 CORRUPTED** · turbo4 OK |

Failure signature is degenerate repetition of CJK punctuation:
`"Linus Torvald。s ... open-source，so anyone can。 View。。，。，。，。，。，..."`

Note `30d6881eb` is *"Merge pull request #212 from apollo-mg/sm60-fp32-carveout"* — they are running
a build that contains our own merged PR.

## What we ran

Two full matrices, **same source, same commit (`c26cbdffc`, 9971), same card, same model file** —
only the backend differs. That isolates backend from codec, which their single data point cannot.

- **Arm A: HIP/ROCm** (`build/`) — our existing build
- **Arm B: Vulkan/RADV** (`build_vulkan/`) — built for this test, `GGML_VULKAN=ON GGML_HIP=OFF`,
  confirmed enumerating `Vulkan0: AMD Radeon RX 9070 XT (RADV GFX1201)`

Probe: their exact prompt ("Write a 500-word essay about Linux."), temp 0, 500 max tokens,
`cache_prompt:false`, `-c 16384`, `-fa on -np 1 -ngl 99 --cache-ram 0`.

**Objective gate, not eyeballing:** gzip compression ratio of the output. Degenerate repetition
compresses absurdly well — the `。，。，。，` pattern lands around 0.02–0.05; healthy prose is
~0.35–0.50. Also counts CJK-punctuation runs of length ≥3 directly.

## Result — 12 of 12 cells healthy

| K / V | HIP gzip | Vulkan gzip | |
|---|---|---|---|
| **turbo4 / turbo3** | **0.5251** | **0.5322** | ← their reported failure |
| f16 / f16 | 0.4783 | 0.4648 | control |
| turbo4 / turbo4 | 0.4933 | 0.5141 | |
| turbo4 / turbo2 | 0.5353 | 0.5178 | |
| turbo3 / turbo3 | 0.5161 | 0.5290 | |
| f16 / turbo3 | 0.5145 | 0.5110 | turbo3 V alone |

**Zero CJK-punctuation runs in any cell. No server failed to start. Every arm produced coherent
English prose** (all opened with the same "Here's a thinking process:" trace).

## Reading

**Not a codec bug.** turbo3 is correct on this hardware in every K/V combination, on two
different backends built from the same commit. Whatever breaks on their machine is not in the
turbo3 quantisation math itself.

**Not Vulkan-generic either.** This is the part that needed the second build: a HIP-only
negative would have left "Vulkan turbo3 path is broken" wide open. RADV on RDNA4 is clean, so
the fault is narrower than "the Vulkan backend."

**Remaining candidates, in rough order of likelihood:**

1. **RADV on Polaris (gfx8/GCN4) specifically** — a different shader compiler path entirely from
   RDNA4. This is the single biggest untested variable and matches their hardware exactly.
2. **`-c 256000` context.** They allocate a 256k window; we ran 16k. A turbo3 V-cache indexing
   or overflow bug could easily be depth-dependent and invisible at 16k.
3. **`--n-cpu-moe 36`.** CPU expert offload changes where tensors live and how they move. We ran
   fully GPU-resident. This interacts with KV handling in ways worth ruling out.
4. **Q4_K_M vs our IQ2_M weights.** Least likely — the codec under test is the KV cache, not the
   weights — but it is a real difference.
5. **Build vintage**: they are on prebuilt 9953 (`30d6881eb`), we are on 9971 (`c26cbdffc`),
   ~18 commits newer. It may already be fixed.

## Deltas from their setup (state these when reporting)

| | them | us |
|---|---|---|
| GPU | RX 580, Polaris/GCN4 | RX 9070 XT, RDNA4/gfx1201 |
| backend | Vulkan/RADV | **both** HIP and Vulkan/RADV |
| context | 256,000 | 16,384 |
| MoE offload | `--n-cpu-moe 36` | none, fully GPU-resident |
| weights | Q4_K_M | UD-IQ2_M |
| build | 9953 prebuilt | 9971 self-built |

A negative result across six differences is informative but not conclusive; it narrows the
search rather than closing it.

## Suggested next step for whoever picks this up

The cheapest discriminating test is **context depth on the reporter's own machine**: re-run
their exact command with `-c 16384` instead of `-c 256000`, changing nothing else. If turbo3
goes clean, it is a depth-dependent bug and that is a very tight reproduction. Second cheapest:
drop `--n-cpu-moe 36`.

We have an **RX 580 (Polaris) on the bench rig** and could test candidate 1 directly — the
strongest lead, since it matches their hardware. Not run here because the bench machine was
mid-card-swap for a resale test.

## Provenance

- `~/projects/HermesAgent-20/turbo3_repro.sh` → `turbo3_repro/` (HIP arm)
- `~/projects/HermesAgent-20/turbo3_repro_vk.sh` → `turbo3_repro_vk/` (Vulkan arm)
- Vulkan build: `engines/llama_cpp_turboquant/build_vulkan/`, `GGML_VULKAN=ON GGML_HIP=OFF`,
  Release, configure log `/tmp/vk_configure.log`, build log `/tmp/vk_build.log`
