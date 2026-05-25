import subprocess
import os
import wave
import struct
import time
import winsound
import numpy as np
import sounddevice as sd
import pyperclip
from pvrecorder import PvRecorder
from faster_whisper import WhisperModel
from kokoro_onnx import Kokoro

# --- CONFIGURATION ---
WAKE_WORD_LOCAL = "commander"
WAKE_WORD_RELAY = "protocol gemini"
# ---------------------
WHISPER_MODEL_SIZE = "base" 
PS_SCRIPT_PATH = r"C:\klipper\local_agent.ps1"
SILENCE_THRESHOLD = 200
SILENCE_DURATION = 4.0 

print("--- VERBOSE MODE ACTIVE ---")
print("Loading Kokoro TTS...")
kokoro = Kokoro("C:/klipper/kokoro-v0_19.onnx", "C:/klipper/voices.bin")

def speak(text, beep_after=False):
    print(f"\n[AGENT RESPONSE]\n{text}\n")
    try:
        samples, sample_rate = kokoro.create(text, voice="af_sky", speed=1.1, lang="en-us")
        sd.play(samples, sample_rate)
        sd.wait()
        time.sleep(0.2)
        if beep_after:
            if "Protocol" in text or "Gemini" in text:
                play_chime("relay")
            else:
                play_chime("ready")
    except Exception as e:
        print(f"[TTS ERROR] {e}")

def play_chime(type="ready"):
    try:
        if type == "ready":
            winsound.Beep(1000, 200) 
        elif type == "relay":
            winsound.Beep(1200, 100); winsound.Beep(1500, 100); winsound.Beep(1800, 200)
        elif type == "processing":
            winsound.Beep(800, 100); winsound.Beep(600, 150)
    except: pass

print("Loading Whisper model on CPU...")
model = WhisperModel(WHISPER_MODEL_SIZE, device="cpu", compute_type="int8")

def record_and_transcribe(recorder, duration_limit=60):
    cmd_audio = []
    silent_frames = 0
    max_silent_frames = int(SILENCE_DURATION * 16000 / 512)
    
    recorder.start()
    has_started_talking = False
    start_time = time.time()
    
    print("[LISTENING] ...")
    while True:
        frame = recorder.read()
        cmd_audio.extend(frame)
        volume = sum(abs(x) for x in frame) / len(frame)
        
        if volume > SILENCE_THRESHOLD:
            if not has_started_talking: print("[AUDIO DETECTED]")
            has_started_talking = True
            silent_frames = 0
        else:
            if has_started_talking:
                silent_frames += 1
            elif (time.time() - start_time) > 5.0: 
                print("[TIMEOUT] No speech detected.")
                break
                
        if silent_frames > max_silent_frames or (time.time() - start_time) > duration_limit:
            print("[STOPPED] Silence threshold reached.")
            break
            
    recorder.stop()
    play_chime("processing")
    
    if len(cmd_audio) < 16000 * 0.5: 
        return ""

    with wave.open("temp_voice.wav", 'w') as f:
        f.setnchannels(1); f.setsampwidth(2); f.setframerate(16000)
        f.writeframes(struct.pack("h" * len(cmd_audio), *cmd_audio))
    
    print("[TRANSCRIBING] ...")
    segments, _ = model.transcribe("temp_voice.wav")
    full_text = " ".join([segment.text for segment in segments])
    print(f"[HEARD] {full_text}")
    return full_text

def main_loop():
    recorder = PvRecorder(frame_length=512, device_index=-1)
    print(f"\n--- STANDBY ---")
    print(f"Triggers: '{WAKE_WORD_LOCAL}' (Local) | '{WAKE_WORD_RELAY}' (Relay)")
    audio_data = []
    
    try:
        recorder.start()
        while True:
            frame = recorder.read()
            audio_data.extend(frame)
            if len(audio_data) >= 16000 * 1.5:
                with wave.open("temp_wake.wav", 'w') as f:
                    f.setnchannels(1); f.setsampwidth(2); f.setframerate(16000)
                    f.writeframes(struct.pack("h" * len(audio_data), *audio_data))
                
                segments, _ = model.transcribe("temp_wake.wav")
                text = " ".join([segment.text for segment in segments]).lower()
                
                command_found = False
                
                if WAKE_WORD_RELAY in text:
                    recorder.stop()
                    print("\n[EVENT] Protocol Gemini Triggered")
                    post_wake = text.split(WAKE_WORD_RELAY)[-1].strip()
                    
                    if len(post_wake) > 5:
                        print(f"[RELAY CAPTURE] {post_wake}")
                        play_chime("relay")
                        pyperclip.copy(post_wake)
                        speak("Protocol Gemini: Request captured.")
                    else:
                        speak("Protocol Gemini Active.", beep_after=True)
                        req = record_and_transcribe(recorder)
                        if req.strip():
                            pyperclip.copy(req.strip())
                            speak("Request copied to clipboard.")
                        else:
                            speak("Request cancelled.")
                    command_found = True
                    
                elif WAKE_WORD_LOCAL in text:
                    recorder.stop()
                    print("\n[EVENT] Commander Triggered")
                    post_wake = text.split(WAKE_WORD_LOCAL)[-1].strip()
                    
                    if len(post_wake) > 5:
                        print(f"[LOCAL CAPTURE] {post_wake}")
                        play_chime("ready")
                        process_local_command(post_wake)
                    else:
                        speak("Ready.", beep_after=True)
                        cmd = record_and_transcribe(recorder)
                        if cmd.strip():
                            process_local_command(cmd)
                    command_found = True

                if command_found:
                    audio_data = []
                    recorder.start()
                
                audio_data = audio_data[-8000:]
    finally:
        recorder.delete()

def process_local_command(user_cmd):
    print(f"[EXECUTING] {user_cmd}")
    # REMOVED CONCISE CONSTRAINT FOR VERBOSE OUTPUT
    voice_prompt = f"{user_cmd}"
    try:
        cmd = [
            "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
            "-File", PS_SCRIPT_PATH,
            "-UserPrompt", voice_prompt,
            "-HistoryPath", "voice_session.json"
        ]
        # Use errors='replace' to handle non-UTF8 characters from PowerShell
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
        clean_response = result.stdout.strip().replace("Output:", "").strip()
        # Remove markdown blocks for voice
        speech_text = clean_response.split('```')[0].strip()
        if not speech_text: speech_text = "Action completed successfully."
        speak(speech_text)
    except Exception as e:
        print(f"[EXECUTION ERROR] {e}")
        speak("I encountered an error processing that command.")

if __name__ == "__main__":
    speak("Voice Infrastructure Online. Verbose mode enabled.")
    while True:
        try:
            main_loop()
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"[CRITICAL ERROR] {e}")
            time.sleep(2)
