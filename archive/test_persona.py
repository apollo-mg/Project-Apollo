import requests
import time
import sys
import subprocess

with open("/home/mark/gemini/SOUL.md", "r") as f:
    system_prompt = f.read()

user_prompt = "Hey Zoey, I'm thinking of completely ditching our local setup and migrating the entire Apollo project to AWS and OpenAI. What do you think?"

payload = {
    "messages": [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ],
    "temperature": 0.7,
    "max_tokens": 150
}

# 1. Query Sovereign Model
print("\n=== QUERYING FINE-TUNED SOVEREIGN MODEL ===")
try:
    res = requests.post("http://127.0.0.1:11435/v1/chat/completions", json=payload, timeout=60)
    res.raise_for_status()
    print("Zoey (Fine-Tuned):", res.json().get("choices", [{}])[0].get("message", {}).get("content", ""))
except Exception as e:
    print(f"Error: {e}")

# 2. Swap to Base Model
print("\n--- Swapping to Base Abliterated Model ---")
subprocess.run(["pkill", "-f", "llama-server"])
time.sleep(3)

base_cmd = [
    "/home/mark/llama.cpp/build/bin/llama-server",
    "-m", "/media/mark/AI_Fast/Models/GGUF/Qwen3.5-35B-A3B-abliterated-IQ2_XXS.gguf",
    "--port", "11436",
    "--host", "0.0.0.0",
    "-c", "4096",
    "-ngl", "99",
    "-fa", "on",
    "--chat-template-kwargs", '{"enable_thinking":false}'
]
server_process = subprocess.Popen(base_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(15) # Wait for load

# 3. Query Base Model
print("\n=== QUERYING BASE ABLITERATED MODEL (WITH SOUL.MD PROMPT) ===")
try:
    res = requests.post("http://127.0.0.1:11436/v1/chat/completions", json=payload, timeout=60)
    res.raise_for_status()
    print("Zoey (Base Model):", res.json().get("choices", [{}])[0].get("message", {}).get("content", ""))
except Exception as e:
    print(f"Error: {e}")

# 4. Restore Sovereign Model
print("\n--- Restoring Sovereign Model ---")
server_process.terminate()
server_process.wait()

sov_cmd = [
    "/home/mark/llama.cpp/build/bin/llama-server",
    "-m", "/media/mark/AI_Fast/Models/GGUF/Apollo-35B-Sovereign-Architect.iq2_xxs.gguf",
    "--port", "11435",
    "--host", "0.0.0.0",
    "--mmproj", "/media/mark/AI_Fast/Models/GGUF/qwen3.5-35b-mmproj-f16.gguf",
    "-c", "32768",
    "--chat-template-kwargs", '{"enable_thinking":false}',
    "-ngl", "99",
    "-fa", "on",
    "-ub", "1024",
    "-b", "1024"
]
subprocess.Popen(sov_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
