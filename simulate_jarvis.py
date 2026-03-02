import os
import sys
import requests
from kokoro_onnx import Kokoro
import sounddevice as sd
import numpy as np

# Mocking the Jarvis Logic for Simulation
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "deepseek-r1:14b"
KOKORO_MODEL_PATH = "/home/mark/commander/kokoro-v0_19.onnx"
KOKORO_VOICES_PATH = "/home/mark/commander/voices.bin"

def get_llm_response(prompt):
    print(f"[Sim] Sending Prompt to DeepSeek: '{prompt}'")
    try:
        response = requests.post(OLLAMA_URL, json={
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False
        }, timeout=30)
        full_text = response.json().get("response", "")
        if "<think>" in full_text:
            full_text = full_text.split("</think>")[-1].strip()
        return full_text
    except Exception as e:
        return f"Error talking to Ollama: {e}"

def simulate_tts(text):
    print(f"[Sim] Testing TTS with: '{text[:50]}...'")
    try:
        kokoro = Kokoro(KOKORO_MODEL_PATH, KOKORO_VOICES_PATH)
        samples, sample_rate = kokoro.create(text, voice="am_michael", speed=1.1, lang="en-us")
        print(f"[Sim] Generated {len(samples)} audio samples successfully.")
        return True
    except Exception as e:
        print(f"[Sim] TTS Bug Detected: {e}")
        return False

def run_simulation():
    test_cases = [
        "What is the status of the shop inventory?",
        "How do I fix a HIP illegal memory access error on RDNA 4?",
        "Jarvis, tell me a story about a robot who learned to weld.",
        "Check 1, 2, 3. Testing emojis and special characters: Rocket Ship and Smile."
    ]

    print("--- Starting Jarvis Simulation ---")
    for i, test in enumerate(test_cases):
        print(f"\n[Test {i+1}]")
        ai_response = get_llm_response(test)
        print(f"[Sim] AI Response: {ai_response[:100]}...")
        
        success = simulate_tts(ai_response)
        if success:
            print(f"[Test {i+1}] Result: PASSED")
        else:
            print(f"[Test {i+1}] Result: FAILED")

if __name__ == "__main__":
    run_simulation()
