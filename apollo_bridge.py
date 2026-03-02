from fastapi import FastAPI, Request
import uvicorn
import buddy_agent
import requests
import os
import sys
import re
import threading
import numpy as np
import sounddevice as sd
from kokoro_onnx import Kokoro
import subprocess
import warnings
from pydantic import BaseModel

# Suppress annoying warnings
warnings.filterwarnings("ignore")

# --- CONFIGURATION ---
KOKORO_MODEL_PATH = "/home/mark/commander/kokoro-v0_19.onnx"
KOKORO_VOICES_PATH = "/home/mark/commander/voices.bin"
SOUND_DIR = "/home/mark/commander/sounds"

app = FastAPI()

# --- INITIALIZE TTS (KOKORO) ---
print("Loading Kokoro TTS for Zoey Bridge...")
kokoro = Kokoro(KOKORO_MODEL_PATH, KOKORO_VOICES_PATH)
IS_SPEAKING = False

class CommandRequest(BaseModel):
    text: str

def play_sound(name):
    path = os.path.join(SOUND_DIR, f"{name}.wav")
    if os.path.exists(path):
        subprocess.Popen(["aplay", "-q", path], stderr=subprocess.DEVNULL)

def speak(text):
    """Speaks text in a background thread."""
    def _speak_thread(t):
        global IS_SPEAKING
        IS_SPEAKING = True
        print(f"[Zoey Bridge] Speaking: {t}")
        # Clean the text for TTS
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

@app.post("/command")
async def process_command(req: CommandRequest):
    user_cmd = req.text.strip()
    if not user_cmd:
        return {"response": "No text received."}
    
    print(f"\n[Satellite Command] Received: {user_cmd}")
    play_sound("processing")
    
    # Process with Buddy Agent (Reasoning Mind)
    response, _ = buddy_agent.chat_with_buddy(user_cmd)
    
    # Clean up the response for TTS
    clean_text = response.split("```")[0].strip()
    if "<think>" in clean_text:
        clean_text = clean_text.split("</think>")[-1].strip()
    
    # Speak on desktop speakers
    speak(clean_text)
    
    return {"response": clean_text}

@app.get("/health")
async def health():
    return {"status": "ok", "agent": "Zoey Bridge"}

@app.post("/wake")
async def wake_signal():
    print("[Satellite Bridge] Wake signal received. Playing 'ready' sound...")
    play_sound("ready")
    return {"status": "acknowledged"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000)
