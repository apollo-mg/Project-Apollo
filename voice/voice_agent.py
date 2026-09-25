#!/usr/bin/env python3
"""Local voice agent: NVIDIA NeMo-Speech.cpp (ASR + diarization + TTS on the RX 9070 XT via Vulkan) + an OpenAI-compatible
LLM (default: .73's Qwen3.8-27B through the wake proxy).

  mic -> ws /v1/audio/transcriptions/realtime (speaker_diarization) -> "Speaker N: ..." -> LLM (streamed)
      -> sentences -> POST /v1/audio/speech (Magpie) -> speakers

Half-duplex: while the agent talks, the mic stream is replaced by silence so it does not transcribe itself.
Start the speech server first (see voice/README.md), then:
  voice_agent.py                       # live mic
  voice_agent.py --list-devices
  voice_agent.py --input-wav q.wav --save-dir out/   # headless test: a WAV in, the spoken replies saved as WAVs
"""
import argparse, asyncio, io, json, os, re, sys, time, wave
import httpx, numpy as np, websockets

SYSTEM = ("You are a friendly voice assistant in a room with one or more people. Each user turn is a transcript in "
          "which words are labelled by anonymous voice ids (Speaker 1, Speaker 2, ...). The same id is the same "
          "voice for the whole session. If someone says their name, remember which speaker id it belongs to and "
          "use it. Your replies are spoken aloud: keep them short and conversational (one to three sentences), no "
          "markdown, no lists, no emoji. If the transcript looks garbled, ask briefly.")
SENT = re.compile(r"(.+?[.!?])(\s+|$)", re.S)

def speaker_runs(ev):
    """Group a final transcription event's words into consecutive runs by speaker."""
    words = ev.get("words") or []
    if not words:
        t = (ev.get("transcript") or "").strip()
        return [("?", t)] if t else []
    runs = []
    for w in words:
        s = w.get("speaker", "?")
        if runs and runs[-1][0] == s:
            runs[-1][1].append(w["word"])
        else:
            runs.append((s, [w["word"]]))
    return [(s, " ".join(ws)) for s, ws in runs]

class Agent:
    def __init__(self, a):
        self.a = a
        self.history = [{"role": "system", "content": SYSTEM}]
        self.speaking = asyncio.Event()           # set while TTS audio is playing
        self.http = httpx.AsyncClient(timeout=httpx.Timeout(300, connect=10))
        self.n_out = 0

    async def speak(self, text):
        r = await self.http.post(f"{self.a.speech}/v1/audio/speech",
                                 json={"model": "magpietts", "input": text, "voice": self.a.voice, "response_format": "wav"})
        r.raise_for_status()
        if self.a.save_dir:
            os.makedirs(self.a.save_dir, exist_ok=True); self.n_out += 1
            open(os.path.join(self.a.save_dir, f"reply_{self.n_out:03d}.wav"), "wb").write(r.content)
        if self.a.no_play:
            return
        import sounddevice as sd
        w = wave.open(io.BytesIO(r.content))
        pcm = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
        await asyncio.to_thread(lambda: (sd.play(pcm, w.getframerate(), device=self.a.output_device), sd.wait()))

    async def respond(self, user_text):
        self.history.append({"role": "user", "content": user_text})
        body = {"model": self.a.model, "messages": self.history[-self.a.max_turns * 2 - 1:] if len(self.history) > self.a.max_turns * 2 + 1
                else self.history, "stream": True, "temperature": 0.7, "max_tokens": 300,
                "chat_template_kwargs": {"enable_thinking": False}}
        if self.history[0] not in body["messages"]:
            body["messages"] = [self.history[0]] + body["messages"]
        reply, buf, t0, first = "", "", time.time(), None
        self.speaking.set()
        try:
            async with self.http.stream("POST", f"{self.a.llm}/v1/chat/completions", json=body) as r:
                async for line in r.aiter_lines():
                    if not line.startswith("data: ") or line.strip() == "data: [DONE]":
                        continue
                    try:
                        delta = json.loads(line[6:])["choices"][0]["delta"].get("content") or ""
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue
                    if first is None and delta:
                        first = time.time() - t0
                    reply += delta; buf += delta
                    while (m := SENT.match(buf)):          # speak each finished sentence as it arrives
                        sentence, buf = m.group(1).strip(), buf[m.end():]
                        print(f"  agent> {sentence}", flush=True)
                        await self.speak(sentence)
            if buf.strip():
                print(f"  agent> {buf.strip()}", flush=True); await self.speak(buf.strip())
        finally:
            self.speaking.clear()
        self.history.append({"role": "assistant", "content": reply.strip()})
        print(f"  [llm first token {first or 0:.1f}s, total {time.time() - t0:.1f}s]", flush=True)

    async def run(self):
        url = self.a.speech.replace("http", "ws", 1) + "/v1/audio/transcriptions/realtime"
        async with websockets.connect(url, max_size=None) as ws:
            await ws.recv()                                               # session.created
            await ws.send(json.dumps({"type": "session.update", "session": {
                "sample_rate": 16000, "speaker_diarization": True, "endpointing_ms": self.a.endpointing_ms}}))
            sender = asyncio.create_task(self.feed_file(ws) if self.a.input_wav else self.feed_mic(ws))
            print("listening... (Ctrl+C to stop)" if not self.a.input_wav else f"feeding {self.a.input_wav}", flush=True)
            async for msg in ws:
                ev = json.loads(msg)
                t = ev.get("type", "")
                if t.endswith("transcription.delta") and not self.a.quiet:
                    print(f"\r  ...{(ev.get('delta') or ev.get('transcript') or '')[-70:]:70s}", end="", flush=True)
                elif t.endswith("transcription.completed"):
                    runs = speaker_runs(ev)
                    if not runs or self.speaking.is_set():
                        continue
                    text = "\n".join(f"Speaker {s}: {w}" for s, w in runs)
                    print("\r" + " " * 80 + "\r" + "\n".join(f"  you [{s}]> {w}" for s, w in runs), flush=True)
                    await self.respond(text)
                    if self.a.input_wav and sender.done():
                        break
                elif t == "error":
                    print("server error:", ev, file=sys.stderr)
            sender.cancel()

    async def feed_mic(self, ws):
        import sounddevice as sd
        q = asyncio.Queue(); loop = asyncio.get_running_loop()
        silence = bytes(3200)                                             # 100 ms of 16 kHz int16
        def cb(indata, frames, t, status):
            loop.call_soon_threadsafe(q.put_nowait, bytes(indata))
        with sd.RawInputStream(samplerate=16000, channels=1, dtype="int16", blocksize=1600,
                               device=self.a.input_device, callback=cb):
            while True:
                chunk = await q.get()
                await ws.send(silence if self.speaking.is_set() else chunk)

    async def feed_file(self, ws):
        w = wave.open(self.a.input_wav)
        assert w.getframerate() == 16000 and w.getnchannels() == 1 and w.getsampwidth() == 2, "need 16 kHz mono int16"
        pcm = w.readframes(w.getnframes()) + bytes(3200 * 20)             # + 2 s of silence to close the turn
        for i in range(0, len(pcm), 3200):
            while self.speaking.is_set():
                await asyncio.sleep(0.1)
            await ws.send(pcm[i:i + 3200]); await asyncio.sleep(0.1)     # real time
        await ws.send(json.dumps({"type": "input_audio_buffer.commit"}))

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--speech", default="http://127.0.0.1:8210", help="NeMo-Speech.cpp server")
    ap.add_argument("--llm", default="http://127.0.0.1:8099", help="OpenAI-compatible LLM base URL (default: .73 wake proxy)")
    ap.add_argument("--model", default="qwen3.8-27b", help="model name sent to the LLM server")
    ap.add_argument("--voice", default="Aria", help="Magpie voice: John, Sofia, Aria, Jason, Leo")
    ap.add_argument("--endpointing-ms", type=int, default=700, help="silence that ends a turn")
    ap.add_argument("--max-turns", type=int, default=20, help="conversation turns kept in context")
    ap.add_argument("--input-device", default=None); ap.add_argument("--output-device", default=None)
    ap.add_argument("--list-devices", action="store_true")
    ap.add_argument("--input-wav", help="headless test: stream this 16 kHz mono WAV instead of the mic")
    ap.add_argument("--save-dir", help="also save every spoken reply as a WAV here")
    ap.add_argument("--no-play", action="store_true", help="do not play audio (headless)")
    ap.add_argument("--quiet", action="store_true", help="hide live partial transcripts")
    a = ap.parse_args()
    if a.list_devices:
        import sounddevice as sd; print(sd.query_devices()); return
    try:
        asyncio.run(Agent(a).run())
    except KeyboardInterrupt:
        print("\nbye")

if __name__ == "__main__":
    main()
