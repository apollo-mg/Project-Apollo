import os
import sys
from kokoro_onnx import Kokoro

KOKORO_MODEL_PATH = "/home/mark/commander/kokoro-v0_19.onnx"
KOKORO_VOICES_PATH = "/home/mark/commander/voices.bin"

def list_voices():
    if not os.path.exists(KOKORO_MODEL_PATH) or not os.path.exists(KOKORO_VOICES_PATH):
        print(f"Error: Kokoro files not found in /home/mark/commander/")
        return

    kokoro = Kokoro(KOKORO_MODEL_PATH, KOKORO_VOICES_PATH)
    voices = kokoro.get_voices()
    print("Available Kokoro Voices:")
    for v in voices:
        print(f" - {v}")

if __name__ == "__main__":
    list_voices()
