# Note -- GLM-5.3-Flash runs on mainline llama.cpp on 4x P100 (.194): UD-IQ3_XXS, auto-fit placement, 4.4 tok/s decode

**2026-09-30.** A "does it work" baseline before buun's EXL3 support (BACKLOG N15). Not pre-registered.

- **Build:** mainline `ggml-org/llama.cpp` at `81ff93e` (b516), which contains the GLM-5.3-Flash merge #27773
  (`649dcb10`, merged 09-30). Built in `~/llama.cpp-upstream/build_sm60`: CUDA 12.4, sm_60, gcc-13 host compiler.
- **Model:** unsloth/GLM-5.3-Flash-GGUF @ `621d456e`, **UD-IQ3_XXS** (120.36 GB), with Unsloth's `Shard_Rewrite/` first
  shard for mainline's `glm5-next` naming. All four files sha256-verified (`MANIFEST_unsloth_UD-IQ3_XXS_mainline.txt`).
- **Size choice:** IQ3_XXS is the GGUF closest to turboderp's EXL3 3.05 bpw (125.3 GB, already on .194), so the two
  compare at matched size later.
- **Tensor table:** 46 blocks (the last is the MTP/nextn block, "unused ... ignoring" on mainline, which has no GLM
  MTP yet: #27917 is open). **43 expert layers at 2.62 GB each (112.5 GB); everything else is 7.87 GB.**

## Results

- **Placement:** an explicit `-ngl 99 -sm layer --n-cpu-moe 30` fails. Layer split gives the last layers to GPUs 2-3,
  and `-ncmoe` keeps only the *last* layers' experts on GPU, so they all pile onto two cards: `allocating 16405.94 MiB
  on device 2: cudaMalloc failed` (`mainline_iq3xxs_ncmoe30_oom.log`).
- **Mainline's automatic fit** (`-fit` default on, no `-ngl`/`-ncmoe`) placed 14.7-15.2 GB per card and put the rest
  of the experts on the CPU (mmap). It loaded in ~100 s.
- **Answers:** correct, and GLM always reasons. Its template has no off switch: `reasoning_effort` accepts low or high,
  otherwise "max". Asked for the SI unit of magnetic flux it said weber, named after Wilhelm Weber (right), but defined
  it as "one tesla per square meter" (wrong: T*m^2).
- **Decode:** **4.38-4.48 tok/s** (3 prompts x 2 passes, 256 tokens, `reasoning_effort` low; `mainline_iq3xxs_speed.jsonl`).
  Major page faults ~100 per request on pass 1 and 0 on pass 2, at the same speed: not a page-cache effect this time.
  Prompt processing of short prompts runs at 6-7 tok/s.
- **Config:** 150 W / 1063 MHz, `-c 16384`, `-np 1`, default KV (f16), mainline defaults otherwise.

## Not established

- Why decode is 4.4 tok/s (a CPU expert path? thread count or NUMA? RAM bandwidth?). The fit pass's exact placement
  was not logged at this verbosity.
- Anything about quality beyond one answer.
- This is the reference the EXL3 3.05 bpw on buun has to beat once buun supports the architecture.
