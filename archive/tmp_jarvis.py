import os
import sys
import time
import json
import requests
import numpy as np
import sounddevice as sd
from kokoro_onnx import Kokoro
import subprocess
import re
import warnings
from datetime import datetime
import io
import wave
import threading

# Suppress annoying warnings
warnings.filterwarnings("ignore")

# --- CONFIGURATION ---
WHISPER_SERVER_URL = "http://127.0.0.1:8080/inference"
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "deepseek-r1:14b"
KOKORO_MODEL_PATH = "/home/mark/commander/kokoro-v0_19.onnx"
KOKORO_VOICES_PATH = "/home/mark/commander/voices.bin"
DOSSIER_PATH = "shop_dossier.json"
PENDING_PATH = "pending_knowledge.json"
SOUND_DIR = "/home/mark/commander/sounds"

# --- GLOBAL STATE ---
history = []
NOISE_HISTORY = []
WAKE_WORD = "zoey"
SAMPLE_RATE = 16000
CHUNK_SIZE = 1024
SILENCE_DURATION = 1.2
MAX_RECORD_TIME = 15.0
IS_SPEAKING = False

# Load Dossier
dossier_content = "{}"
if os.path.exists(DOSSIER_PATH):
    with open(DOSSIER_PATH, "r") as f:
        dossier_content = f.read()

# --- INITIALIZE TTS (KOKORO) ---
print("Loading Kokoro TTS...")
kokoro = Kokoro(KOKORO_MODEL_PATH, KOKORO_VOICES_PATH)

def transcribe_audio(audio_data):
    """Sends raw numpy audio data to the local whisper.cpp server."""
    wav_buffer = io.BytesIO()
    with wave.open(wav_buffer, 'wb') as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(SAMPLE_RATE)
        if audio_data.size == 0: return {"text": ""}
        audio_int16 = (audio_data * 32767).astype(np.int16)
        f.writeframes(audio_int16.tobytes())
    
    wav_buffer.seek(0)
    files = {'file': ('audio.wav', wav_buffer, 'audio/wav')}
    data = {'response_format': 'json', 'temperature': '0.0'}
    
    try:
        response = requests.post(WHISPER_SERVER_URL, files=files, data=data, timeout=5)
        if response.status_code == 200:
            return {"text": response.json().get('text', '').strip()}
    except requests.exceptions.ConnectionError:
        print("\n[Zoey Error] Cannot connect to Whisper server. Did you run ./start_whisper.sh?")
    except Exception as e:
        print(f"\n[STT API Error] {e}")
    return {"text": ""}

def play_sound(name):
    path = os.path.join(SOUND_DIR, f"{name}.wav")
    if os.path.exists(path):
        if sys.platform == "win32":
            import winsound
            winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
        else:
            subprocess.Popen(["aplay", "-q", path], stderr=subprocess.DEVNULL)
    else:
        sys.stdout.write('\a')
        sys.stdout.flush()

def get_dynamic_threshold():
    global NOISE_HISTORY, IS_SPEAKING
    if not NOISE_HISTORY: return 0.04
    sorted_noise = sorted(NOISE_HISTORY)
    # Be much more aggressive about the baseline to ignore fans/hums
    baseline = sorted_noise[int(len(sorted_noise) * 0.5)] 
    # Require a much larger spike above baseline to trigger
    margin = 0.25 if IS_SPEAKING else 0.04
    # Set a hard minimum floor so it never triggers on silence
    return max(baseline + margin, 0.04)

def record_until_silence(stream, input_channels, native_sample_rate):
    print("\n[Zoey] Listening...")
    play_sound("ready")
    audio_data = []
    silent_chunks = 0
    has_started = False
    start_time = time.time()
    
    # Calculate chunk size based on native sample rate to keep timing consistent
    ratio = int(native_sample_rate / SAMPLE_RATE)
    local_chunk_size = CHUNK_SIZE * ratio
    
    while True:
        chunk, _ = stream.read(local_chunk_size)
        mono_chunk = chunk[:, 0] if input_channels > 1 else chunk.flatten()
        
        # Simple decimation for downsampling if ratio > 1
        if ratio > 1:
            mono_chunk = mono_chunk[::ratio]
            
        audio_data.append(mono_chunk)
        
        vol = np.max(np.abs(mono_chunk))
        threshold = get_dynamic_threshold()
        
        meter = "#" * int(vol * 50)
        status = "[WAITING]" if not has_started else "[HEARING]"
        sys.stdout.write(f"\033[K\rVol: [{meter:<25}] {status} Thresh: {threshold:.4f} ")
        sys.stdout.flush()

        if vol > threshold:
            has_started = True
            silent_chunks = 0
        else:
            if has_started:
                silent_chunks += 1
        
        if has_started and silent_chunks > (SILENCE_DURATION * (SAMPLE_RATE / CHUNK_SIZE)):
            break
        
        if not has_started and (time.time() - start_time) > 5.0:
            print("\n[Zoey] Timeout (No speech detected).")
            break
            
        if (time.time() - start_time) > MAX_RECORD_TIME:
            print("\n[Zoey] Max record time reached.")
            break
    
    return np.concatenate(audio_data).flatten()

import buddy_agent

def get_llm_response(prompt):
    global history
    print(f"\n[Zoey] Thinking (System 2)...")
    
    clean_prompt = prompt.lower().strip()
    if "clear all pending knowledge" in clean_prompt:
        if os.path.exists(PENDING_PATH):
            with open(PENDING_PATH, "w") as f:
                json.dump([], f)
        return "Understood. I have cleared the pending knowledge buffer for you."

    try:
        response, _ = buddy_agent.chat_with_buddy(prompt)
        clean_text = response.split("```")[0].strip()
        if "<think>" in clean_text:
            clean_text = clean_text.split("</think>")[-1].strip()
        return clean_text
    except Exception as e:
        return f"Error in agent reasoning: {e}"

def speak(text):
    """Speaks text in a background thread."""
    def _speak_thread(t):
        global IS_SPEAKING
        IS_SPEAKING = True
        print(f"[Zoey] Speaking: {t}")
        t = re.sub(r'[\*\#\_]', '', t)
        t = re.sub(r'[^\x00-\x7F]+', ' ', t)
        t = re.sub(r'\s+', ' ', t).strip()
        
        if not t: 
            IS_SPEAKING = False
            return

        try:
            voice_name = "bf_lily"
            samples, sample_rate = kokoro.create(t, voice=voice_name, speed=1.1, lang="en-gb")
            sd.stop()
            sd.play(samples, sample_rate)
            sd.wait()
        except Exception as e:
            print(f"TTS Error: {e}")
        finally:
            IS_SPEAKING = False

    threading.Thread(target=_speak_thread, args=(text,), daemon=True).start()

def main():
    global NOISE_HISTORY
    print("\n--- Initializing Local Zoey (ROCm GPU) ---")
    
    # We use a single mic for both Wake and Command since the boom mic is too directional
    devices = sd.query_devices()
    input_device = None
    priority_keywords = ["USB Camera", "C922", "Webcam", "Playstation Eye", "Zoey_Input"]
    for kw in priority_keywords:
        for i, dev in enumerate(devices):
            if kw.lower() in dev['name'].lower() and dev['max_input_channels'] > 0:
                input_device = i; break
        if input_device is not None: break
    if input_device is None: input_device = sd.default.device[0]
    print(f"✅ Using Mic: [{input_device}] {devices[input_device]['name']}")

    device_info = devices[input_device]
    input_channels = int(device_info['max_input_channels'])
    
    # Use native sample rate and downsample if needed
    native_sr = int(device_info['default_samplerate'])
    ratio = int(native_sr / SAMPLE_RATE)
    local_chunk_size = CHUNK_SIZE * ratio

    print(f"--- CALIBRATING NOISE FLOOR (2s) on {input_channels} channels ---")
    with sd.InputStream(device=input_device, samplerate=native_sr, channels=input_channels, dtype='float32') as stream:
        for _ in range(int(2.0 * SAMPLE_RATE / CHUNK_SIZE)):
            chunk, _ = stream.read(local_chunk_size)
            mono_chunk = chunk[:, 0] if input_channels > 1 else chunk.flatten()
            if ratio > 1: mono_chunk = mono_chunk[::ratio]
            vol = np.max(np.abs(mono_chunk))
            NOISE_HISTORY.append(vol)
            meter = "#" * int(vol * 50)
            sys.stdout.write(f"\033[K\rLevel: [{meter:<25}] {vol:.4f}")
            sys.stdout.flush()
    
    print(f"\nNoise Floor Set (Thresh: {get_dynamic_threshold():.4f})")
    print(f"Listening for '{WAKE_WORD}'...")

    wake_buffer = []
    last_check_time = 0
    
    try:
        with sd.InputStream(device=input_device, samplerate=native_sr, channels=input_channels, dtype='float32') as stream:
            while True:
                chunk, _ = stream.read(local_chunk_size)
                mono_chunk = chunk[:, 0] if input_channels > 1 else chunk.flatten()
                if ratio > 1: mono_chunk = mono_chunk[::ratio]
                
                vol = np.max(np.abs(mono_chunk))
                NOISE_HISTORY.append(vol)
                if len(NOISE_HISTORY) > 500: NOISE_HISTORY.pop(0)
                
                wake_buffer.append(mono_chunk)
                max_buffer_chunks = int(3.0 * SAMPLE_RATE / CHUNK_SIZE)
                if len(wake_buffer) > max_buffer_chunks:
                    wake_buffer = wake_buffer[-max_buffer_chunks:]

                threshold = get_dynamic_threshold()
                current_time = time.time()
                
                if vol > threshold and (current_time - last_check_time) > 1.2:
                    if len(wake_buffer) > (1.5 * SAMPLE_RATE / CHUNK_SIZE):
                        extra_chunks = int(0.6 * SAMPLE_RATE / CHUNK_SIZE)
                        for _ in range(extra_chunks):
                            chunk, _ = stream.read(local_chunk_size)
                            mono_chunk = chunk[:, 0] if input_channels > 1 else chunk.flatten()
                            if ratio > 1: mono_chunk = mono_chunk[::ratio]
                            wake_buffer.append(mono_chunk)
                        
                        audio_check = np.concatenate(wake_buffer).flatten()
                        result = transcribe_audio(audio_check)
                        text = result["text"].lower().strip(".,? ")
                        sys.stdout.write("\033[K")
                        print(f"\r[Zoey] Heard: '{text}'")
                        last_check_time = time.time()
                        
                        phonetic_matches = ["zoe", "zoey", "zoie", "zowy", "zo e", "zo-e", "zoë", "zowie", "zoee", "so e", "soie", "soey"]
                        
                        if any(variant in text for variant in phonetic_matches):
                            sd.stop() 
                            print(f"\n[WAKE WORD DETECTED] (Input: '{text}')")
                            
                            audio_cmd = record_until_silence(stream, input_channels, native_sr)
                            
                            play_sound("processing")
                            print("\n[Zoey] Transcribing...")
                            res_cmd = transcribe_audio(audio_cmd)
                            user_cmd = res_cmd["text"].strip()
                            
                            if user_cmd:
                                print(f"> You: {user_cmd}")
                                ai_text = get_llm_response(user_cmd)
                                speak(ai_text)
                            
                            wake_buffer = []
                            print(f"\nListening for '{WAKE_WORD}'...")

    except KeyboardInterrupt:
        print("\nStopping Local Zoey...")

if __name__ == "__main__":
    main()
