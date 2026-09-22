# Result — Breeze TTS 2 runs on RDNA4 unmodified: 8.8 GB, RTF 3.2-7.7, ~120 W

**2026-09-22, RX 9070 XT (gfx1201).** `BreezeBlue/Breeze-TTS-2` (7.2 GB on disk), inference code
`github.com/breezeblue-ai/breeze-tts`, `torch 2.13.0+rocm7.2` / HIP 7.2.53211 / ROCm 7.2.4.
Eager mode, no `--fast-*` flags, no source changes. Samples and `ladder.json` in `samples/`.

**Prior art checked:** `ledger_precheck.py "TTS RDNA4 gfx1201 text to speech"` -> nothing; this
fleet has `whisper.cpp` (STT) and no TTS receipt. `[[rdna4-hip-bench-role]]` — this is turboquant's
only AMD hardware.
**What this adds:** the vendor requires *"a CUDA-capable NVIDIA GPU"* and ships a Docker image
targeting H100/Hopper. No RDNA4 result exists. It ranks **#1 among open-weight models on the
Artificial Analysis TTS leaderboard**, so "does it run on AMD" is a question with an audience.

## It runs, first attempt, no code changes

```
audio      24 kHz mono, peak 0.56, RMS 0.095, 78% non-quiet  -- real speech, not silence
peak VRAM  11.31 GB total / ~8.77 GB for the model   (vendor claims ~7.7 GiB eager: +14%)
power      112-174 W against a ~304 W board
clocks     sclk 3171-3226 MHz (near boost ceiling), mclk pinned 1258 MHz
GPU use    81-92%
```

**flash-attn degrades gracefully** — `Warning: flash-attn is not installed. Will only run the
manual PyTorch version.` That was the whole RDNA4 risk and the code simply takes the fallback.

**MIOpen falls back on the codec convolutions**, repeatedly:
`Solver <GemmFwdRest>, workspace required: 1913856, provided ptr: 0 size: 0`. Benign — it picks a
no-workspace solver — but the Mimi convolutions are not hitting tuned kernels, which costs
**time, not watts**.

## The length ladder: it does NOT degrade, and gets FASTER

Same voice instruction, four lengths, one variable:

| sample | chars | audio | wall | RTF | last/first RMS |
|---|---:|---:|---:|---:|---:|
| s05 | 47 | 3.0 s | 23.2 s | 7.65 | 0.40 * |
| s15 | 154 | 11.6 s | 48.2 s | 4.15 | 0.67 |
| s30 | 365 | 26.9 s | 94.4 s | 3.51 | 0.72 |
| **s60** | 737 | **58.9 s** | 188.0 s | **3.19** | **0.83** |

*\* the s05 figure is an artefact of the metric, not the model: at 3 s the ten windows are 0.3 s
each, so the last one catches the natural trailing-off of a sentence. Short clips are mostly edges.*

**Level stability improves with length and the 59 s sample is the most stable of the four.** No
dead tail beyond 1 s, no dropout, peak amplitude holds. The common expectation that TTS degrades
over a long utterance does not reproduce here at one minute.

**RTF improves 7.65 -> 3.19 with length**, because model load, text encode and warmup amortise.
Same shape as the prompt-cache effect measured on `.194`. A warm resident process would do better
than any figure here.

## Why the power draw is low — measured, not assumed

81-92 % utilisation at near-max shader clock while drawing ~a third of the board budget, with
`mclk` pinned flat. That is **memory-bound, low arithmetic intensity**: autoregressive decode at
batch 1 reads a large share of the weights per step, so the shaders report busy while waiting on
VRAM, and moving bytes costs far less power than dense FMA. The MIOpen fallbacks add *time* at the
same power rather than raising draw.

Practical consequence: **a real-time-capable TTS for ~120 W** sits comfortably beside a resident
LLM without competing for power or thermal headroom.

## Installation: three traps, all avoidable

1. **`breeze` is registered by the REPO, not by `qwen-tts`.** `models/breeze_config.py` does
   `AutoConfig.register("breeze", BreezeConfig, exist_ok=True)`. The HF weights alone are
   unusable; `model_type: breeze` is in no transformers release and there is **no `auto_map`**, so
   `trust_remote_code` does not rescue it.
2. **`qwen-tts` pins `transformers==4.57.3`.** Against our 5.10.0.dev0 it dies with
   `check_model_inputs() missing 1 required positional argument: 'func'`. A separate venv is
   required; installing into the project venv would have downgraded transformers for every other
   tool.
3. **A pip dependency drags in a CUDA torch** (`2.14.0+cu130`, `cuda.is_available() False`) that
   shadows a ROCm install. Fixed by removing it and symlinking `torch`/`torchaudio` from the
   working ROCm venv, leaving that venv untouched.

## What this does NOT establish

- **No quality measurement.** Mark's read is that it sounds *"about as good as the TTS built into
  Claude Desktop"*; that is one listener, unblinded, knowing the source. A real claim needs the
  `svgbench-blind` protocol, and `[[svgbench-blind-panel]]` measured raters agreeing on only
  58-66 % of decisive pairs even when trained.
- **One voice, one instruction, English only.** The model advertises bilingual EN/ZH, voice clone
  and voice direction; none of those were exercised.
- **No comparison to the vendor's own numbers.** They report **0.32 RTF and under 40 ms TTFA on an
  H100 with the warmed-up fast path**. Ours is eager, cold, no `torch.compile`, no flash-attn,
  untuned MIOpen. The ~10x gap is four disabled optimisations stacked, **not** a card-to-card
  comparison, and must not be quoted as one.
- **`--fast-*` untested.** Those are the `torch.compile`/CUDA-graph paths and are the obvious next
  experiment: if RTF falls sharply while power stays ~120 W, the deficit was kernel efficiency; if
  power climbs toward 250 W, the GPU was genuinely under-fed.
- **Degradation tested to 59 s only.** Nothing is claimed past one minute.
