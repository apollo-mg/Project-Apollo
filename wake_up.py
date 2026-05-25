import os
import sys
import time
import wave
import subprocess
import pyaudio
import webrtcvad
import numpy as np
from openwakeword.model import Model
import openwakeword
from modules.theme import stylized_print, CLR_CYAN, CLR_GOLD, CLR_RED, CLR_RESET

# ========================================================
# SOVEREIGN AUDIO PIPELINE: LISTENER & RECORDER
# ========================================================

WAKE_WORD = "hey_jarvis_v0.1" # Dictionary key returned by openwakeword
WHISPER_BIN = "./whisper.cpp/build/bin/whisper-cli"
WHISPER_MODEL = "./whisper.cpp/models/ggml-base.en.bin"
AUDIO_FILE = "data/command.wav"

FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000 # 16kHz is required by both openwakeword and webrtcvad
CHUNK = 1280 # 80ms chunk for smooth wakeword processing

def check_whisper_model():
    if not os.path.exists(WHISPER_MODEL):
        stylized_print("alert", f"Whisper model not found at {WHISPER_MODEL}", color=CLR_RED)
        print("Please run this command to download the base English model:")
        print("cd whisper.cpp && bash ./models/download-ggml-model.sh base.en")
        sys.exit(1)
    if not os.path.exists(WHISPER_BIN):
        stylized_print("alert", f"Whisper binary not found at {WHISPER_BIN}. Did you run 'make' inside whisper.cpp?", color=CLR_RED)
        sys.exit(1)

def main():
    check_whisper_model()
    
    # Initialize PyAudio
    audio = pyaudio.PyAudio()
    mic_stream = audio.open(format=FORMAT,
                            channels=CHANNELS,
                            rate=RATE,
                            input=True,
                            frames_per_buffer=CHUNK)

    # Initialize OpenWakeWord
    stylized_print("system", "Loading OpenWakeWord Neural Net...", color=CLR_CYAN)
    model_paths = openwakeword.get_pretrained_model_paths()
    jarvis_path = next(p for p in model_paths if "hey_jarvis" in p)
    owwModel = Model(wakeword_model_paths=[jarvis_path])

    # Initialize WebRTC VAD (Voice Activity Detection)
    vad = webrtcvad.Vad()
    vad.set_mode(3) # 0=Normal, 1=Low Bitrate, 2=Aggressive, 3=Very Aggressive (Filters background noise best)

    stylized_print("system", "SOVEREIGN EARS ONLINE. Listening for 'Hey Jarvis'...", color=CLR_GOLD)

    try:
        while True:
            # 1. THE LISTENER LOOP (Waiting for Wakeword)
            audio_data = np.frombuffer(mic_stream.read(CHUNK, exception_on_overflow=False), dtype=np.int16)
            
            # Feed audio to OpenWakeWord
            prediction = owwModel.predict(audio_data)
            
            # Check if threshold is met (0.5 is usually a good default)
            if prediction[WAKE_WORD] > 0.5:
                stylized_print("event", "WAKEWORD DETECTED. Starting command recording...", color=CLR_GOLD)
                
                # We need smaller chunks for VAD (10ms, 20ms, or 30ms)
                # 30ms at 16000Hz = 480 frames
                VAD_CHUNK = 480 
                

                frames = []
                silence_chunks = 0
                max_silence_chunks = int((1.5 * RATE) / VAD_CHUNK) # 1.5 seconds of silence

                # ADDED: Max recording chunks (e.g., 10 seconds total)
                max_recording_chunks = int((10.0 * RATE) / VAD_CHUNK)
                total_chunks = 0

                # Start recording the command
                while True:
                    data = mic_stream.read(VAD_CHUNK, exception_on_overflow=False)
                    frames.append(data)
                    total_chunks += 1

                    is_speech = vad.is_speech(data, RATE)

                    if not is_speech:
                        silence_chunks += 1
                    else:
                        silence_chunks = 0 # reset silence counter

                    # BREAK CONDITION 1: Natural Silence
                    if silence_chunks > max_silence_chunks:
                        stylized_print("event", "Silence detected. Stopping recording.", color=CLR_CYAN)
                        break

                    # BREAK CONDITION 2: Hard Timeout (Prevent infinite recording loops)
                    if total_chunks > max_recording_chunks:
                        stylized_print("alert", "Max recording time reached. Cutting off.", color=CLR_RED)
                        break

                # Save the recorded command
                wf = wave.open(AUDIO_FILE, 'wb')
                wf.setnchannels(CHANNELS)
                wf.setsampwidth(audio.get_sample_size(FORMAT))
                wf.setframerate(RATE)
                wf.writeframes(b''.join(frames))
                wf.close()

                # 3. THE SCRIBE (Whisper.cpp)
                stylized_print("system", "Transcribing audio...", color=CLR_CYAN)
                whisper_cmd = [
                    WHISPER_BIN,
                    "-m", WHISPER_MODEL,
                    "-f", AUDIO_FILE,
                    "-nt", # No timestamps in output
                    "--no-prints" # Quiet mode, only print the transcript
                ]
                
                result = subprocess.run(whisper_cmd, capture_output=True, text=True)
                transcript = result.stdout.strip()
                
                if transcript and transcript != "[BLANK_AUDIO]":
                    stylized_print("input", f"\"{transcript}\"", color=CLR_GOLD)
                    
                    # 4. THE BRAIN (Buddy Agent)
                    # Stop the mic stream temporarily while the agent speaks to prevent feedback loops
                    mic_stream.stop_stream()
                    
                    stylized_print("system", "Routing to Buddy Agent...", color=CLR_CYAN)
                    subprocess.run([sys.executable, "buddy_agent.py", transcript])
                    
                    mic_stream.start_stream()
                else:
                    stylized_print("alert", "No usable speech transcribed.", color=CLR_RED)
                
                stylized_print("system", "Returning to standby... Listening for 'Hey Jarvis'.", color=CLR_CYAN)
                # Flush the audio buffer so we don't double-trigger
                mic_stream.read(mic_stream.get_read_available(), exception_on_overflow=False)

    except KeyboardInterrupt:
        print("\n[*] Shutting down Sovereign Ears.")
    finally:
        mic_stream.stop_stream()
        mic_stream.close()
        audio.terminate()

if __name__ == "__main__":
    main()
