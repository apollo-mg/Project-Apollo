# Local voice agent (NeMo-Speech.cpp on the RX 9070 XT + Qwen3.8 on .73)

Speech runs entirely on the desktop through NVIDIA's NeMo-Speech.cpp (ggml, **Vulkan**): streaming ASR, speaker
diarization and TTS. The LLM is `.73`'s Qwen3.8-27B through the wake proxy (`:8099`), so `.73` wakes on the first
turn.

```
mic -> realtime ASR + diarization (words tagged Speaker 1..4) -> "Speaker N: ..." -> Qwen3.8 (streamed, thinking off)
    -> sentence by sentence -> Magpie TTS -> speakers
```

## 1. Start the speech server (desktop)

```bash
cd /mnt/TG_2TB/Projects/nemo-speech
build/vulkan-server/bin/nemo-speech serve --host 127.0.0.1 --port 8210 --device vulkan \
  --asr-model nemotron-3.5 --diar-model nemotron-3-diarization --tts-model magpie
# ready when: curl -s localhost:8210/ready  ->  {"capabilities":["asr","diarization","tts"],"device":"vulkan","ready":true}
# the playground UI is at http://127.0.0.1:8210/
```

Build notes (2026-09-25, GCC 16, CMake 4.4): `git submodule update --init --recursive ggml third_party/cpp-httplib
llama.cpp`, then `scripts/build_sentencepiece_static.sh` and `scripts/configure.sh vulkan-server` with
`CMAKE_POLICY_VERSION_MINIMUM=3.5 CXXFLAGS="-include cstdint"`, then `cmake --build --preset vulkan-server` (92 s). Models
(`nemo-speech pull`, hash-verified): ASR `nemotron-3.5` (708 MB), TTS `magpie` (438 MB) with `nano-codec` (76 MB),
diarizer `nemotron-3-diarization` (103 MB).

## 2. Run the agent

```bash
cd /mnt/TG_2TB/Projects/Apollo
./venv_cachyos/bin/python3 voice/voice_agent.py                  # live mic, default voice Aria
./venv_cachyos/bin/python3 voice/voice_agent.py --list-devices   # pick --input-device / --output-device if needed
./venv_cachyos/bin/python3 voice/voice_agent.py --voice Leo --endpointing-ms 900
```

- Voices: John, Sofia, Aria, Jason, Leo.
- **Speakers:** each utterance's words are grouped by the diarizer's speaker id and sent as `Speaker 1: ...` /
  `Speaker 2: ...`. Say "I'm Mark" and it will map your voice id to your name for the rest of the session.
- **Half-duplex:** while the agent talks, the mic is replaced by silence, so it does not hear itself. There is no
  barge-in yet.
- A turn ends after `--endpointing-ms` of silence (default 700).
- **Noisy room (fan, A/C, PCs):** a PipeWire drop-in, `~/.config/pipewire/pipewire.conf.d/60-voice-echo-cancel.conf`,
  adds a virtual mic `voice_ec_source` running WebRTC noise suppression, AGC, high-pass and echo cancellation (the
  reference is the default speaker's monitor). The agent records from it automatically through `pw-record` when it
  exists (`--pw-source ''` falls back to the sounddevice default). Capture follows the system default mic, which the
  drop-in does not change.
- Utterances with mean word confidence < `--min-confidence` (0.6), or a lone word < 0.9, are ignored as noise.
  Clean speech scores 1.0.

## Measured (2026-09-25, headless test with `--input-wav`)

- Magpie TTS: 3.9 s of audio in 1.0 s (~4x real time, 22.05 kHz).
- A spoken question -> exact transcript with a speaker tag -> reply. With `.73` warm, the LLM's first token arrived
  **0.2 s** after the turn ended, and the whole reply, including the first sentence's TTS, was ready in **1.7 s**.
  With `.73` asleep, the first turn waits for its wake + load (~55 s).

## Ideas

- Barge-in: keep listening while speaking, and stop playback when a new user speech start arrives.
- Point `--llm` at a local model on the 9070 for no-network latency (VRAM is shared with the speech models, ~2.5 GB).
- Hermes: its `stt`/`tts` config could use this server's OpenAI-compatible `/v1/audio/transcriptions` and
  `/v1/audio/speech`.
