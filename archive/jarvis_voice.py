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
import buddy_agent  # Shop Buddy / General Expert

# Try importing dependencies
try:
    import numpy as np
    import sounddevice as sd
    from pvrecorder import PvRecorder
    from faster_whisper import WhisperModel
    from kokoro_onnx import Kokoro
except ImportError as e:
    print(f"Missing dependency: {e}")
    print("Please run: pip install numpy sounddevice pvrecorder faster-whisper kokoro-onnx")
    sys.exit(1)

# --- CONFIGURATION ---
WAKE_WORD_LOCAL = "jarvis"
WAKE_WORD_RELAY = "protocol gemini"
WHISPER_MODEL_SIZE = "base.en" 
TEMP_DIR = os.path.join(os.getcwd(), "tmp")
SOUND_DIR = os.path.join(os.getcwd(), "sounds")
SILENCE_DURATION = 0.8 

# Ensure directories exist
os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(SOUND_DIR, exist_ok=True)

# Global History for Noise Floor
NOISE_HISTORY = []

def play_wav(path):
    if sys.platform == "win32":
        import winsound
        winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
    else:
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
try:
    kokoro = Kokoro(KOKORO_MODEL, KOKORO_VOICES)
except Exception as e:
    print(f"TTS Init Failed: {e}")
    kokoro = None

def speak(text, beep_after=False):
    print(f"\nAgent: {text}")
    if not kokoro: return
    clean_text = re.sub(r'[\*\#\_]', '', text)
    sentences = [s.strip() for s in re.split(r'(?<=[.!?]) +', clean_text) if s.strip()]
    audio_queue = queue.Queue()

    def generate_worker():
        try:
            for sentence in sentences:
                if not sentence.strip(): continue
                # Generate audio
                samples, sample_rate = kokoro.create(sentence, voice="am_michael", speed=1.2, lang="en-us")
                
                # Resample if needed (Kokoro is 24k, we want 48k for system mixer)
                if sample_rate == 24000:
                    target_rate = 48000
                    duration = len(samples) / sample_rate
                    target_length = int(duration * target_rate)
                    x_old = np.linspace(0, duration, len(samples))
                    x_new = np.linspace(0, duration, target_length)
                    samples = np.interp(x_new, x_old, samples).astype(np.float32)
                
                samples = np.trim_zeros(samples, 'b')
                # Push to queue
                audio_queue.put(samples)
            audio_queue.put(None) # Signal end
        except Exception as e:
            print(f"Generation Error: {e}")
            audio_queue.put(None)

    gen_thread = threading.Thread(target=generate_worker)
    gen_thread.start()

    def playback_worker():
        try:
            while True:
                chunk = audio_queue.get()
                if chunk is None: break
                sd.play(chunk, 48000)
                sd.wait() 
            if beep_after:
                if "Gemini" in text: play_sound("relay")
                else: play_sound("ready")
        except Exception as e:
            print(f"TTS Playback Error: {e}")

    play_thread = threading.Thread(target=playback_worker)
    play_thread.start()

# STT Setup
print(f"Loading Whisper model ({WHISPER_MODEL_SIZE}) on CPU...")
model = WhisperModel(WHISPER_MODEL_SIZE, device="cpu", compute_type="int8")

def get_dynamic_threshold():
    global NOISE_HISTORY
    if not NOISE_HISTORY: return 100
    # Use 10th percentile as noise floor baseline
    sorted_noise = sorted(NOISE_HISTORY)
    baseline = sorted_noise[int(len(sorted_noise) * 0.1)]
    
    # Margin of 300 above baseline, minimum 450
    return max(baseline + 300, 450)

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

def record_and_transcribe(recorder, duration_limit=30):
    global NOISE_HISTORY
    cmd_audio = []
    silent_frames = 0
    max_silent_frames = int(SILENCE_DURATION * 31.25)
    
    recorder.start()
    has_started_talking = False
    start_time = time.time()
    
    while True:
        frame = recorder.read()
        cmd_audio.extend(frame)
        volume = sum(abs(x) for x in frame) / len(frame)
        
        # Update noise history even while recording (for future thresholds)
        NOISE_HISTORY.append(volume)
        if len(NOISE_HISTORY) > 200: NOISE_HISTORY.pop(0)
        
        threshold = get_dynamic_threshold()
        
        if volume > threshold:
            sys.stdout.write(f"\rVol: {volume:4.0f} [ACTIVE] Thresh: {threshold:4.0f} ")
            has_started_talking = True
            silent_frames = 0
        else:
            sys.stdout.write(f"\rVol: {volume:4.0f} [......] Thresh: {threshold:4.0f} ")
            if has_started_talking:
                silent_frames += 1
            elif (time.time() - start_time) > 4.0: 
                break
        
        sys.stdout.flush()
        if silent_frames > max_silent_frames: break
        if (time.time() - start_time) > duration_limit: break
            
    recorder.stop()
    print("\n[PROCESSING] ...")
    play_sound("processing")
    if len(cmd_audio) < 16000 * 0.5: return ""
    return transcribe_buffer(cmd_audio)

def process_command(user_cmd):
    # 0. Strip self-hearing "Ready"
    clean_cmd = user_cmd.strip(" .,?!")
    if clean_cmd.lower().startswith("ready"):
        clean_cmd = clean_cmd[5:].strip(" .,?!")
    
    # 1. Strip repetitive hallucinations (e.g. "No. No. No.")
    words = clean_cmd.split()
    if len(words) > 10:
        # Check if the last 5 words are identical
        if words[-1] == words[-2] == words[-3]:
            # Remove the tail
            clean_cmd = " ".join([w for i, w in enumerate(words) if i == 0 or w != words[i-1]])
    
    user_cmd = clean_cmd
    print(f"\nCommand: {user_cmd}")
    is_scan = "scan" in user_cmd.lower() and "vault" not in user_cmd.lower()
    visual_triggers = ["webcam", "camera", "what is this", "take a picture", "identify this", "look at this", "web camp"]
    
    if is_scan or any(w in user_cmd.lower() for w in visual_triggers):
         speak("Scanning part via webcam.")
    response, _ = buddy_agent.chat_with_buddy(user_cmd)
    speak(response.replace('```', '').strip())

def main_loop():
    global NOISE_HISTORY
    try:
        devices = PvRecorder.get_available_devices()
        device_index = -1
        for i, dev in enumerate(devices):
            if "C922" in dev: device_index = i; break
            elif "Playstation Eye" in dev or "Sony" in dev: device_index = i; break
            elif "Shop_Ears" in dev: device_index = i; break            
        recorder = PvRecorder(frame_length=512, device_index=device_index)
        print(f"✅ Using Mic: {devices[device_index]}")
    except Exception as e:
        print(f"Failed to init device: {e}"); return

    print(f"Listening for '{WAKE_WORD_LOCAL}'...")
    audio_data = []
    
    try:
        recorder.start()
        while True:
            frame = recorder.read()
            audio_data.extend(frame)
            vol = sum(abs(x) for x in frame) / len(frame)
            
            # Continuous Noise Floor Tracking
            NOISE_HISTORY.append(vol)
            if len(NOISE_HISTORY) > 200: NOISE_HISTORY.pop(0) # 6.4 seconds of history
            
            threshold = get_dynamic_threshold()
            
            if vol > threshold and int(time.time() * 10) % 5 == 0:
                sys.stdout.write(".")
                sys.stdout.flush()
            
            time.sleep(0.01)

            if len(audio_data) > 16000 * 5: audio_data = audio_data[-16000 * 5:]

            if len(audio_data) >= 16000 * 1.5:
                # Use a larger buffer for the wake word check
                text = transcribe_buffer(audio_data).lower()
                
                if WAKE_WORD_LOCAL in text or WAKE_WORD_RELAY in text:
                    recorder.stop()
                    print("\n[WAKE WORD DETECTED]")
                    
                    post_wake = text.split(WAKE_WORD_LOCAL)[-1].strip() if WAKE_WORD_LOCAL in text else text.split(WAKE_WORD_RELAY)[-1].strip()
                    post_wake = post_wake.strip(".,?! ")
                    
                    if len(post_wake) > 5:
                        play_sound("ready")
                        process_command(post_wake)
                    else:
                        speak("Ready.", beep_after=True)
                        cmd = record_and_transcribe(recorder)
                        if cmd.strip(): process_command(cmd)
                        else: speak("Cancelled.")
                    
                    audio_data = []
                    time.sleep(0.5)
                    recorder.start()
                else:
                    audio_data = audio_data[-8000:]
                        
    finally:
        recorder.delete()

def main():
    speak("System online.")
    while True:
        try:
            main_loop()
        except KeyboardInterrupt: break
        except Exception as e:
            print(f"Loop Error: {e}")
        time.sleep(3)

if __name__ == "__main__":
    main()
