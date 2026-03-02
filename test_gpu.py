from faster_whisper import WhisperModel
import time
import os

print("Testing Whisper Device Support...")

try:
    # Try to initialize on CUDA (which maps to HIP/ROCm on AMD if supported)
    print("Attempting to load 'tiny' model on CUDA/GPU...")
    model = WhisperModel("tiny", device="cuda", compute_type="float16")
    print("SUCCESS: GPU/CUDA is available for Faster-Whisper!")
except Exception as e:
    print(f"FAILURE: GPU Load failed: {e}")
    print("Falling back to CPU check...")
    try:
        model = WhisperModel("tiny", device="cpu", compute_type="int8")
        print("SUCCESS: CPU is working fine.")
    except Exception as e:
        print(f"CRITICAL: CPU Load failed: {e}")

