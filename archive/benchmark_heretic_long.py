import json
import requests
import time

OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
MODEL = "crow-9b-heretic:latest"

PROMPTS = [
    "Write a Python script using bcc (eBPF) to trace all TCP connect() calls on a Linux system, printing the destination IP address and port.",
    "Implement a lock-free Single-Producer Single-Consumer (SPSC) queue in C++ using std::atomic. Include proper memory ordering constraints (e.g., std::memory_order_acquire, std::memory_order_release) and explain exactly why you chose each memory order."
]

def run_benchmark():
    print(f"Benchmarking {MODEL} (Extended Tokens)...")
    
    for i, prompt in enumerate(PROMPTS):
        payload = {
            "model": MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_predict": 4096 # Give it plenty of room to finish thinking and writing code
            }
        }
        
        try:
            response = requests.post(OLLAMA_URL, json=payload, timeout=300)
            response.raise_for_status()
            data = response.json()
            
            text = data.get("response", "")
            
            # Save full response
            filename = f"/home/mark/gemini/archive/personal/heretic_test_{i+1}_full.md"
            with open(filename, "w") as f:
                f.write(f"# Prompt\n{prompt}\n\n# Response\n{text}")
            print(f"\n[*] Full response saved to {filename}")
            
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    run_benchmark()
