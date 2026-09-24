# Nemotron-3-Diarization runs on CPU through NeMo-Speech.cpp: 4/4 speakers, 1.1 % speaker confusion, slightly slower than real time on 4 Xeon threads

**2026-09-24**, `.194` CPU only (2x Xeon E5-2650 v3; the GPUs were busy with another run). Model card:
NVIDIA Ampere+ only, NeMo framework. Runtime used instead: **NeMo-Speech.cpp** `97a15af` (NVIDIA's ggml-based C++
runtime, ggml `c03b4e2`), preset `cpu-diar`, default settings. Model `Nemotron-3-Diarization.q8_0.gguf`
(107,012,128 B, sha256 `08456d9e22cd9a32...`, pulled and SHA-verified by the tool).

**A sanity check, not a benchmark:** one meeting, default thresholds, one run.

## Test audio

AMI meeting **ES2004a**, Mix-Headset (CC BY 4.0), 17.5 min, 16 kHz mono, 4 speakers.
- Audio sha256 `3e2560b19bee6952...`.
- Reference: pyannote `AMI-diarization-setup` `only_words/rttms/test/ES2004a.rttm`, sha256 `9869c6146c2fd959...`.

AMI is **not** among the datasets on NVIDIA's card (DIHARD III, CALLHOME, AliMeeting, NOTSOFAR), so this is an
out-of-card check. Raw: `raw/nemo_ES2004a.rttm` (hypothesis), `raw/ES2004a.rttm` (reference). Scorer: `der.py`
(`pyannote.metrics`).

## Result

| scoring | DER | missed | false alarm | **confusion** |
|---|---:|---:|---:|---:|
| collar 0, overlap scored | 21.22 % | 14.08 | 6.06 | **1.07** |
| collar 0.25 s | 16.55 % | 13.54 | 2.56 | 0.45 |
| collar 0.25 s, overlap excluded | 14.41 % | 10.90 | 3.17 | 0.33 |

- **4 of 4 speakers found.** When it attributes speech, it is almost always to the right person (confusion
  0.3-1.1 %).
- The error is dominated by **missed speech**: short utterances and overlap left unlabelled at the default onset
  threshold. That is the tunable part (`--onset`, `--min-duration-on`); it was not tuned here.

## Speed and footprint (defaults)

- 17.5 min of audio in **19 min 15 s** of wall time: real-time factor **1.10**.
- **395 % CPU**: the default uses ~4 threads of 40, so this is an out-of-box floor, not the machine's capability.
- **428 MB RSS.**

## Build notes (to reproduce on a stock Ubuntu with GCC 15 and CMake 4)

Nothing was installed system-wide:
1. `ninja` via `uv tool install ninja`.
2. SentencePiece via the repo's `scripts/build_sentencepiece_static.sh`. It needs:
   - `CMAKE_POLICY_VERSION_MINIMUM=3.5` (CMake 4 rejects SentencePiece's old minimum);
   - `CXXFLAGS="-include cstdint"` (GCC 15 no longer pulls in `<cstdint>` transitively: `'uint32_t' does not name
     a type`).
3. `scripts/configure.sh cpu-diar && cmake --build --preset cpu-diar` (same `CXXFLAGS`).

## What this adds

The card says NVIDIA Ampere+ only. The ggml runtime runs it on a CPU from 2014 at close to real time, in under
half a GB of RAM, with near-perfect speaker attribution on an out-of-card meeting. Same family as
`rdna4-tts/RESULT_BREEZE_TTS2_RDNA4.md` (a vendor-NVIDIA speech model running where the card says it won't).

## Not established

- One meeting.
- Default thresholds.
- The thread count was not tuned.
- The Vulkan build on the RX 9070 XT (the obvious next step) is untested.
- No comparison against another diarizer on the same audio.
