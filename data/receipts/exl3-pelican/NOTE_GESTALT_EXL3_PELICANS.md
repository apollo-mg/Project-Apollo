# Note — GestaltLabs EXL3 11.5GB pelicans, INFORMAL and deliberately not a panel arm

**2026-09-21 17:00-17:03, RX 9070 XT (gfx1201).** buun **`38ada0e1b`** (master, built today;
see the configure break below), `GestaltLabs/Qwen3.8-27B-EXL3-11.5GB` with its **embedded
`mtp.*` heads** (39 MTP tensors confirmed in the index; `--spec-type draft-mtp
--spec-mtp-vocab-size 32768`, no sidecar). `-c 16384 -ngl 99 -fa on -ctk f16 -ctv f16 -np 1`,
14,187 MiB resident. Prompt and temperature match the panel — *"Generate an SVG of a pelican
riding a bicycle."*, temperature 1.0 — **but this is 3 reps with thinking off, where the panel
runs 5 reps per arm with each arm's shipped template.**

**It is not an arm and must not be scored beside one.** Folding this model into the svgbench
blind panel needs a dated amendment and a fresh blind round with the outside raters, exactly as
`qwen4exp/pelican_informal/README.md` says for Flash-Next.

Raw: `gestalt_exl3_20260921.jsonl`, `rep{1,2,3}.svg`, `rep{1,2,3}.png`.

## The runs

| rep | tokens | tok/s | secs | SVG chars | reasoning chars | finish |
|---|---:|---:|---:|---:|---:|---|
| 1 | 2,024 | 58.99 | 34.3 | 4,050 | **0** | stop |
| 2 | 2,060 | 58.41 | 35.3 | 4,280 | **0** | stop |
| 3 | 2,205 | 58.82 | 37.5 | 4,444 | **0** | stop |

**Thinking-off was verified, not assumed.** `enable_thinking` via `chat_template_kwargs` is
deprecated on current buun and was measured **inert** for AgentWorld earlier today
(`argus-v2/RESULT_AGENTWORLD_AS_GENERATOR.md`), so the runner records `reasoning_content`
length per rep. All three are 0.

## The read (written, because the v1 scorer is not trustworthy here)

`qwen4exp/NOTE_SVGBENCH_SCORER_COUNTEREXAMPLE.md` found the v1 scorer **never rewards a revision
and twice punishes one** on drawings a human immediately calls better. So these are described
rather than scored.

| rep | read |
|---|---|
| **1** | **Best pelican.** The only rep with a genuine **pouched** beak — two-tone yellow, pouch line drawn — on a correct long S-curve neck. But the bird **stands on** the bike rather than sitting: legs drop straight to the pedals and the body floats above a frame with no seat under it. Frame is a bare red triangle, not a diamond. |
| **2** | **Best composition.** Bird properly **seated**, body over the frame, legs reaching down to the cranks, wing drawn as a separate shape, and a full scene (sun, clouds, grass). Weakest beak of the three — orange, pointed, **no pouch**, reads stork. The top tube runs into the bird's body, so the frame is incoherent where it matters. |
| **3** | **Best bicycle** by a wide margin — real diamond frame, handlebars with grips, seat, crank and pedal, both wheels properly spoked, and a red cap on the bird that reads as a helmet. Beak is orange with a hint of pouch. Bird is a plain oval with no wing, and small against the frame. |

**No rep did both well, and this replicates the Flash-Next informal finding exactly.** Bird
quality and bicycle quality traded off across all three draws. A single draw would have
mischaracterised the model in either direction, which is the argument for the panel's 5-rep
design.

**Token count again did not predict quality:** the longest rep (2,205) has the weakest bird and
the shortest (2,024) has the best one. Same as Flash-Next, where the longest was the weakest
composition.

## On the speed number

58.4-59.0 tok/s at ~2k-token generations. **This is not comparable to
`rdna4-exl3-kernel/RESULT_EXL3_WMMA.md`'s 42.8-44.4 tok/s** and must not be read as an
improvement over it: that was 128-token generations at a fixed short prompt, this is 2k-token
generations with growing context, and longer runs amortise prefill. **A different measurement
shape, not a regression or a gain** — the same caution the Flash-Next informal note records for
its own 18.6 against the ladder's 22.33.

## Build note, reported upstream

Master `38ada0e1b` **fails to configure** for gfx1201: `HIP_ARCHITECTURES is empty for target
"test-exl3-byte-dot"`. `ggml-hip/CMakeLists.txt:38-40` forwards `GPU_TARGETS` into
`CMAKE_HIP_ARCHITECTURES` with a bare `set()`, which is **directory-scoped**; `ggml` and `tests`
are sibling subdirectories, so it never reaches `tests/`. The CUDA path is immune because it
reads a **target** property off `ggml-cuda`, which is global. Measured: `AMDGPU_TARGETS` fails,
`GPU_TARGETS` fails, only `-DCMAKE_HIP_ARCHITECTURES=gfx1201` works. Draft sent to buun
(`data/drafts/buun_hip_arch_scope_DRAFT.md`).

## What this does NOT establish

- **n = 3, one model, one prompt, informal.** No comparison, no score, no claim about EXL3 versus
  anything.
- **No fidelity measurement.** This model still has **no KLD** on our ladder — the EXL3 quality
  curve was measured on turboderp's builds, and packager and recipe both differ here. "Good for
  its size" remains established on footprint and speed, untested on fidelity.
- **The read is mine and unblinded.** I knew which model produced these, which is exactly the bias
  the blind panel exists to remove.
