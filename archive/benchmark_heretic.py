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
    print(f"Benchmarking {MODEL}...")
    
    for i, prompt in enumerate(PROMPTS):
        print(f"\n{'='*50}")
        print(f"--- Test {i+1}: Hard Coding ---")
        print(f"Prompt: {prompt}")
        print(f"{'='*50}")
        
        payload = {
            "model": MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_predict": 1500 # Ensure it has enough room to think and output code
            }
        }
        
        start_time = time.time()
        try:
            response = requests.post(OLLAMA_URL, json=payload, timeout=120)
            response.raise_for_status()
            data = response.json()
            
            end_time = time.time()
            elapsed = end_time - start_time
            
            text = data.get("response", "")
            eval_count = data.get("eval_count", 0)
            eval_duration_ns = data.get("eval_duration", 0)
            
            if eval_duration_ns > 0:
                tps = eval_count / (eval_duration_ns / 1e9)
            else:
                tps = eval_count / elapsed if elapsed > 0 else 0
                
            print(f"\n[Metrics]")
            print(f"Time Elapsed: {elapsed:.2f} seconds")
            print(f"Tokens Generated: {eval_count}")
            print(f"Speed: {tps:.2f} TPS")
            
            # Print the think block and start of code if present
            print("\n[Response Preview]")
            
            lines = text.split('\n')
            preview_lines = lines[:30] # Show first 30 lines to catch the thought process
            print('\n'.join(preview_lines))
            if len(lines) > 30:
                print("...\n[Response truncated for brevity]")
                
            # Save full response
            filename = f"heretic_test_{i+1}.md"
            with open(filename, "w") as f:
                f.write(f"# Prompt\n{prompt}\n\n# Response\n{text}")
            print(f"\n[*] Full response saved to {filename}")
            
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    run_benchmark()