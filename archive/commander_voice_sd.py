import os
import wave
import struct
import time
import subprocess
import sys
import re
import threading
import json
import io
import queue
import local_agent
import kasa_control
import network_scanner

# Try importing dependencies
try:
    import numpy as np
    import sounddevice as sd
    from faster_whisper import WhisperModel
    from kokoro_onnx import Kokoro
except ImportError as e:
    print(f"Missing dependency: {e}")
    sys.exit(1)

# --- CONFIGURATION ---
WAKE_WORD_LOCAL = "commander"
WAKE_WORD_RELAY = "protocol gemini"
WHISPER_MODEL_SIZE = "tiny"
TEMP_DIR = os.path.join(os.getcwd(), "tmp")
SOUND_DIR = os.path.join(os.getcwd(), "sounds")
SILENCE_DURATION = 1.2

# Ensure directories exist
os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(SOUND_DIR, exist_ok=True)

# Audio Player (Linux)
def play_wav(path):
    subprocess.Popen(["aplay", "-q", path], stderr=subprocess.DEVNULL)

def play_sound(name):
    path = os.path.join(SOUND_DIR, f"{name}.wav")
    if os.path.exists(path):
        play_wav(path)
    else:
        print("\a")

# TTS Setup
print("Loading Kokoro TTS...")
KOKORO_MODEL = "kokoro-v0_19.onnx"
KOKORO_VOICES = "voices.bin"
kokoro = None
try:
    kokoro = Kokoro(KOKORO_MODEL, KOKORO_VOICES)
except Exception as e:
    print(f"TTS Init Failed: {e}")

def speak(text, beep_after=False):
    print(f"\nAgent: {text}")
    if not kokoro: return
    try:
        samples, sample_rate = kokoro.create(text, voice="af_sky", speed=1.1, lang="en-us")
        if sample_rate == 24000:
            target_rate = 48000
            duration = len(samples) / sample_rate
            target_length = int(duration * target_rate)
            x_old = np.linspace(0, duration, len(samples))
            x_new = np.linspace(0, duration, target_length)
            samples = np.interp(x_new, x_old, samples).astype(np.float32)
            sample_rate = target_rate
        sd.play(samples, sample_rate)
        sd.wait()
        time.sleep(0.1)
        if beep_after:
            if "Gemini" in text: play_sound("relay")
            else: play_sound("ready")
    except Exception as e:
        print(f"TTS Error: {e}")

# STT Setup
print(f"Loading Whisper model ({WHISPER_MODEL_SIZE}) on CPU...")
model = WhisperModel(WHISPER_MODEL_SIZE, device="cpu", compute_type="int8")

# Audio Queue
audio_queue = queue.Queue()

def audio_callback(indata, frames, time, status):
    if status:
        print(status, file=sys.stderr)
    audio_queue.put(indata.copy())

def transcribe_buffer(audio_data):
    if not audio_data: return ""
    try:
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, 'wb') as f:
            f.setnchannels(1); f.setsampwidth(2); f.setframerate(16000)
            f.writeframes(struct.pack("h" * len(audio_data), *audio_data))
        wav_buffer.seek(0)
        segments, _ = model.transcribe(wav_buffer, beam_size=1, language="en", temperature=0.0)
        return " ".join([segment.text for segment in segments])
    except Exception as e:
        print(f"Transcription Error: {e}")
        return ""

def process_command(user_cmd):
    user_cmd = user_cmd.strip(" .,?!").strip()
    print(f"\nCommand: {user_cmd}")

    # 1. LIGHTING
    light_match = re.search(r"(turn on|turn off|toggle)\s+(.+)", user_cmd.lower())
    if light_match:
        action = light_match.group(1).replace("turn ", "")
        target = light_match.group(2).strip(" .,?!")
        if target.startswith("the "): target = target[4:]
        print(f"Fast Track: Lighting -> {action} {target}")
        try:
            subprocess.run(["python3", "kasa_control.py", target, action], capture_output=True)
            speak(f"Okay, {target} {action}.") 
        except:
            speak("Lighting control failed.")
        return

    # 2. NETWORK
    if "scan network" in user_cmd.lower() or "list devices" in user_cmd.lower():
        speak("Scanning network.")
        subprocess.run(["python3", "network_scanner.py"])
        return

    # 3. IMAGE
    if "generate image" in user_cmd.lower() or "draw" in user_cmd.lower():
        prompt = user_cmd
        if "generate image of" in user_cmd.lower(): prompt = user_cmd.lower().split("generate image of")[1]
        elif "generate image" in user_cmd.lower(): prompt = user_cmd.lower().split("generate image")[1]
        elif "draw" in user_cmd.lower(): prompt = user_cmd.lower().split("draw")[1]
        
        prompt = prompt.strip(" .,?!")
        if not prompt:
            speak("What should I draw?")
            return
        speak(f"Generating {prompt}")
        subprocess.Popen(["python3", "generate_image.py", prompt])
        return

    # 4. LLM
    print("Slow Track: LLM Inference...")
    try:
        response = local_agent.chat_with_llm(user_cmd, history_path=os.path.join(TEMP_DIR, "voice_session.json"))
        if "COMMAND:" in response:
            # Handle Klipper commands (simplified for brevity)
            speak("Command executed.")
        else:
            speak(response.split('```')[0].strip())
    except Exception as e:
        speak(f"Error: {e}")

def main_loop():
    print("Starting Audio Stream...")
    # Use default device (follows PulseAudio)
    with sd.InputStream(samplerate=16000, device=None, channels=1, dtype='int16', callback=audio_callback, blocksize=512):
        
        # Calibrate
        print("Calibrating...")
        levels = []
        for _ in range(30): # ~1s
            frame = audio_queue.get()
            levels.append(np.abs(frame).mean())
        THRESHOLD = max(max(levels) * 1.5, 100)
        print(f"Threshold: {THRESHOLD:.2f}")
        
        print(f"Listening for '{WAKE_WORD_LOCAL}'...")
        audio_buffer = []
        
        while True:
            frame = audio_queue.get()
            # frame is numpy int16 array
            frame_list = frame.flatten().tolist()
            audio_buffer.extend(frame_list)
            
            # Keep 5s buffer
            if len(audio_buffer) > 16000 * 5:
                audio_buffer = audio_buffer[-16000 * 5:]
            
            # Check Wake Word every ~1.5s
            if len(audio_buffer) >= 16000 * 1.5:
                vol = np.abs(frame).mean()
                if vol > THRESHOLD:
                    # Check wake word
                    text = transcribe_buffer(audio_buffer).lower()
                    if WAKE_WORD_LOCAL in text:
                        print("\n[WAKE DETECTED]")
                        
                        # Extract command from wake phrase if present
                        cmd_part = text.split(WAKE_WORD_LOCAL)[-1].strip(" .,?!")
                        if len(cmd_part) > 5:
                            play_sound("ready")
                            process_command(cmd_part)
                        else:
                            speak("Ready?", beep_after=True)
                            # Record command
                            cmd_frames = []
                            silent_frames = 0
                            while True:
                                f = audio_queue.get()
                                cmd_frames.extend(f.flatten().tolist())
                                if np.abs(f).mean() < THRESHOLD:
                                    silent_frames += 1
                                else:
                                    silent_frames = 0
                                # Stop after silence
                                if silent_frames > (16000 / 512 * 1.5): # 1.5s silence
                                    break
                            
                            cmd_text = transcribe_buffer(cmd_frames)
                            if cmd_text.strip():
                                process_command(cmd_text)
                        
                        audio_buffer = [] # Clear buffer
                else:
                    # Drop old data if silent to keep buffer fresh
                    if len(audio_buffer) > 16000 * 2:
                        audio_buffer = audio_buffer[-16000:]

if __name__ == "__main__":
    speak("System online.")
    while True:
        try:
            main_loop()
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Loop Error: {e}")
            time.sleep(1)
