import os
import sys
import numpy as np
import sounddevice as sd
from kokoro_onnx import Kokoro

KOKORO_MODEL_PATH = "/home/mark/commander/kokoro-v0_19.onnx"
KOKORO_VOICES_PATH = "/home/mark/commander/voices.bin"

def audition():
    if not os.path.exists(KOKORO_MODEL_PATH):
        print("Kokoro model not found.")
        return

    kokoro = Kokoro(KOKORO_MODEL_PATH, KOKORO_VOICES_PATH)
    
    # Selection of distinct female voices to test
    audition_voices = [
        ("af_sarah", "Hi, I'm Sarah. I'm usually described as soft and calm."),
        ("af_nicole", "I'm Nicole. I have a more professional and articulate tone."),
        ("af_sky", "Hey there, I'm Sky! I'm energetic and very expressive."),
        ("bf_alice", "Hello, I'm Alice. I have a clear British accent."),
        ("bf_lily", "Hi, I'm Lily. I'm a slightly softer British voice."),
        ("af_nova", "Hello, I'm Nova. I have a modern, smooth American tone.")
    ]

    print("--- Starting Zoey Voice Audition ---")
    for v_id, text in audition_voices:
        print(f"Testing: {v_id}...")
        try:
            samples, sample_rate = kokoro.create(text, voice=v_id, speed=1.1, lang="en-us" if v_id.startswith("af") else "en-gb")
            sd.play(samples, sample_rate)
            sd.wait()
        except Exception as e:
            print(f"Error testing {v_id}: {e}")
    print("--- Audition Complete ---")

if __name__ == "__main__":
    audition()
