import os
import wave
import struct
import time
import subprocess
import sys
import re
import threading
import json
import local_agent
import kasa_control
import network_scanner

try:
    import numpy as np
    import sounddevice as sd
    import soundfile as sf
    from pvrecorder import PvRecorder
    from faster_whisper import WhisperModel
    from kokoro_onnx import Kokoro
except ImportError as e:
    print(f"Missing dependency: {e}")
    sys.exit(1)

# --- CONFIGURATION ---
WAKE_WORD_LOCAL = "commander"
WAKE_WORD_RELAY = "protocol gemini"
WHISPER_MODEL_SIZE = "base"
TEMP_DIR = os.path.join(os.getcwd(), "tmp")
SOUND_DIR = os.path.join(os.getcwd(), "sounds")
SILENCE_DURATION = 2.0

os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(SOUND_DIR, exist_ok=True)

def play_wav(path):
    subprocess.Popen(["aplay", "-q", path], stderr=subprocess.DEVNULL)

def play_sound(name):
    path = os.path.join(SOUND_DIR, f"{name}.wav")
    if os.path.exists(path):
        play_wav(path)
    else:
        print("\a")

print("Loading Kokoro TTS...")
KOKORO_MODEL = "kokoro-v0_19.onnx"
KOKORO_VOICES = "voices.bin"
if not os.path.exists(KOKORO_MODEL):
    print(f"Warning: {KOKORO_MODEL} not found. TTS will fail.")

try:
    kokoro = Kokoro(KOKORO_MODEL, KOKORO_VOICES)
except Exception as e:
    print(f"TTS Init Failed: {e}")
    kokoro = None

def speak(text, beep_after=False):
    print(f"
Agent: {text}")
    if not kokoro:
        return
    try:
        samples, sample_rate = kokoro.create(text, voice="af_sky", speed=1.1, lang="en-us")
        sf.write("tts_out.wav", samples, sample_rate)
        subprocess.run(["aplay", "-q", "tts_out.wav"])
        time.sleep(0.1)
        if beep_after:
            if "Gemini" in text: play_sound("relay")
            else: play_sound("ready")
    except Exception as e:
        print(f"TTS Error: {e}")

print("Loading Whisper model on CPU...")
model = WhisperModel(WHISPER_MODEL_SIZE, device="cpu", compute_type="int8")

def calibrate_noise_floor(recorder):
    print("
--- CALIBRATING NOISE FLOOR (2s) ---")
    print("Please remain silent...")
    recorder.start()
    levels = []
    start = time.time()
    while time.time() - start < 2.0:
        frame = recorder.read()
        vol = sum(abs(x) for x in frame) / len(frame)
        levels.append(vol)
    recorder.stop()
    avg_noise = sum(levels) / len(levels) if levels else 0
    max_noise = max(levels) if levels else 0
    threshold = max(max_noise + 15, 50)
    print(f"Avg Noise: {avg_noise:.2f} | Threshold: {threshold:.2f}")
    return threshold

def record_and_transcribe(recorder, threshold, duration_limit=30):
    cmd_audio = []
    silent_frames = 0
    max_silent_frames = int(SILENCE_DURATION * 31.25)
    recorder.start()
    has_started_talking = False
    start_time = time.time()
    print(f"[LISTENING] (Threshold: {threshold:.0f})")
    
    while True:
        frame = recorder.read()
        cmd_audio.extend(frame)
        volume = sum(abs(x) for x in frame) / len(frame)
        
        if volume > threshold:
            sys.stdout.write(f"Vol: {volume:4.0f} [ACTIVE] ")
            has_started_talking = True
            silent_frames = 0
        else:
            sys.stdout.write(f"Vol: {volume:4.0f} [......] ")
            if has_started_talking:
                silent_frames += 1
            elif (time.time() - start_time) > 4.0: 
                break
        sys.stdout.flush()
                
        if silent_frames > max_silent_frames: break
        if (time.time() - start_time) > duration_limit: break
            
    recorder.stop()
    print("
[PROCESSING] ...")
    play_sound("processing")
    
    if len(cmd_audio) < 16000 * 0.5: return ""

    temp_voice_path = os.path.join(TEMP_DIR, "temp_voice.wav")
    try:
        with wave.open(temp_voice_path, 'w') as f:
            f.setnchannels(1); f.setsampwidth(2); f.setframerate(16000)
            f.writeframes(struct.pack("h" * len(cmd_audio), *cmd_audio))
        segments, _ = model.transcribe(temp_voice_path)
        return " ".join([segment.text for segment in segments])
    except Exception as e:
        print(f"Transcription Error: {e}")
        return ""

def process_command(user_cmd):
    print(f"
Command: {user_cmd}")
    # Regex Fix: Ignore trailing punctuation
    light_match = re.search(r"^(turn on|turn off|toggle)\s+([a-zA-Z0-9 ]+)", user_cmd.lower().replace(".", "").replace("?", ""))
    if light_match:
        action = light_match.group(1).replace("turn ", "")
        target = light_match.group(2).strip()
        print(f"Lighting Control: {action} -> {target}")
        try:
            cmd = ["python3", "kasa_control.py", target, action]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.stdout.strip(): speak(result.stdout.strip())
            else: speak(f"Could not find device {target}")
        except: speak("Lighting control failed.")
        return

    if "scan network" in user_cmd.lower():
        speak("Scanning network...")
        try:
            cmd = ["python3", "network_scanner.py"]
            result = subprocess.run(cmd, capture_output=True, text=True)
            dev_count = result.stdout.count("FOUND:")
            speak(f"Scan complete. Found {dev_count} devices.")
        except: speak("Scan failed.")
        return

    # LLM
    response = local_agent.chat_with_llm(user_cmd, history_path=os.path.join(TEMP_DIR, "voice_session.json"))
    if "COMMAND:" in response:
        klipper_data = ""
        action_performed = False
        if "COMMAND: STATUS" in response:
            klipper_data = local_agent.get_klipper_data("/printer/objects/query?heater_bed&extruder&print_stats&toolhead")
        elif "COMMAND: STOP" in response:
            local_agent.get_klipper_data("/printer/emergency_stop", method="POST")
            speak("Emergency Stop triggered.")
            return
        elif "COMMAND: PAUSE" in response:
            local_agent.get_klipper_data("/printer/gcode/script?script=PAUSE", method="POST")
            action_performed = True
        elif "COMMAND: RESUME" in response:
            local_agent.get_klipper_data("/printer/gcode/script?script=RESUME", method="POST")
            action_performed = True
        elif "COMMAND: HOME" in response:
            local_agent.get_klipper_data("/printer/gcode/script?script=G28", method="POST")
            action_performed = True
        elif "COMMAND: COOLDOWN" in response:
            local_agent.get_klipper_data("/printer/gcode/script?script=TURN_OFF_HEATERS", method="POST")
            action_performed = True
        
        if action_performed: speak("Command sent.")
        elif klipper_data:
            data_str = json.dumps(klipper_data)
            final_response = local_agent.chat_with_llm(
                f"KLIPPER_DATA: {data_str}

Based on this data, answer: "{user_cmd}"",
                history_path=os.path.join(TEMP_DIR, "voice_session.json")
            )
            speak(final_response.split('```')[0].strip())
        else: speak("Command executed.")
    else:
        speak(response.split('```')[0].strip())

def main_loop():
    try:
        recorder = PvRecorder(frame_length=512, device_index=12) # Index 12 for Gemini
    except Exception as e:
        print(f"Mic Init Failed: {e}")
        return

    THRESHOLD = calibrate_noise_floor(recorder)
    print(f"Listening for '{WAKE_WORD_LOCAL}'...")
    audio_data = []
    
    try:
        recorder.start()
        while True:
            frame = recorder.read()
            audio_data.extend(frame)
            vol = sum(abs(x) for x in frame) / len(frame)
            if vol > THRESHOLD:
                sys.stdout.write(".")
                sys.stdout.flush()
            
            if len(audio_data) > 16000 * 5: audio_data = audio_data[-16000 * 5:]
            
            if len(audio_data) >= 16000 * 1.5:
                temp_wake_path = os.path.join(TEMP_DIR, "temp_wake.wav")
                try:
                    with wave.open(temp_wake_path, 'w') as f:
                        f.setnchannels(1); f.setsampwidth(2); f.setframerate(16000)
                        f.writeframes(struct.pack("h" * len(audio_data), *audio_data))
                    segments, _ = model.transcribe(temp_wake_path)
                    text = " ".join([segment.text for segment in segments]).lower()
                    
                    if WAKE_WORD_LOCAL in text or WAKE_WORD_RELAY in text:
                        recorder.stop()
                        print("
[WAKE WORD DETECTED]")
                        post_wake = text.split(WAKE_WORD_LOCAL)[-1].strip() if WAKE_WORD_LOCAL in text else text.split(WAKE_WORD_RELAY)[-1].strip()
                        post_wake = post_wake.strip(".,?! ")
                        if len(post_wake) > 5:
                            play_sound("ready")
                            process_command(post_wake)
                        else:
                            speak("Ready.", beep_after=True)
                            cmd = record_and_transcribe(recorder, THRESHOLD)
                            if cmd.strip(): process_command(cmd)
                            else: speak("Cancelled.")
                        audio_data = []
                        recorder.start()
                    else:
                        audio_data = audio_data[-8000:]
                except Exception as e:
                    audio_data = []
    finally:
        recorder.delete()

if __name__ == "__main__":
    speak("System online.")
    while True:
        try: main_loop()
        except KeyboardInterrupt: break
        except Exception as e:
            print(f"Loop Error: {e}")
            time.sleep(3)
