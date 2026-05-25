import requests
import json
import time
import subprocess
import os

# Configuration
MODEL_PATH = "models/Nemotron-Cascade-14B-Thinking-Claude-4.5-Opus-Distill.q4_k_m.gguf"
API_URL = "http://127.0.0.1:8082/v1/chat/completions"

PROMPTS = [
    {"name": "Logic Puzzle", "prompt": "A farmer has a wolf, a goat, and a cabbage. He needs to cross a river with them, but his boat can only carry him and one item at a time. If left alone, the wolf will eat the goat, and the goat will eat the cabbage. How can he get all three safely across?"},
    {"name": "Coding (Rust)", "prompt": "Write a highly optimized multithreaded prime number generator in Rust. Ensure you handle synchronization properly."},
    {"name": "Math", "prompt": "Solve for x: 2x^2 - 5x - 3 = 0. Show all steps."}
]

def spin_up_server():
    print(f"[*] Starting llama-server with {MODEL_PATH}...")
    # Stop any existing server just in case
    os.system("pkill -9 llama-server")
    time.sleep(1)
    
    cmd = [
        "llama.cpp/build/bin/llama-server",
        "-m", MODEL_PATH,
        "--port", "8082",
        "-ngl", "99",
        "-c", "4096"
    ]
    process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    # Wait for server to become ready
    for i in range(15):
        try:
            r = requests.get("http://127.0.0.1:8082/health")
            if r.status_code == 200:
                print(f"[*] Server Online! (PID: {process.pid})")
                return process
        except requests.exceptions.ConnectionError:
            pass
        time.sleep(2)
    print("[!] Server failed to start.")
    return process

def run_benchmark(prompt_data):
    print(f"\n--- Testing: {prompt_data['name']} ---")
    payload = {
        "messages": [{"role": "user", "content": prompt_data["prompt"]}],
        "temperature": 0.6,
        "max_tokens": 2048,
        "stream": False
    }
    
    start_time = time.time()
    try:
        response = requests.post(API_URL, json=payload, timeout=300)
        response.raise_for_status()
        end_time = time.time()
        
        data = response.json()
        content = data['choices'][0]['message']['content']
        usage = data.get('usage', {})
        total_tokens = usage.get('total_tokens', 0)
        gen_tokens = usage.get('completion_tokens', 0)
        
        duration = end_time - start_time
        tps = gen_tokens / duration if duration > 0 else 0
        
        print(f"Prompt: {prompt_data['prompt'][:60]}...")
        print(f"Response Preview: {content[:150]}...")
        print(f"[Results] Generation Time: {duration:.2f}s")
        print(f"[Results] Tokens Generated: {gen_tokens}")
        print(f"[Results] Speed: {tps:.2f} tokens/sec")
        return {"name": prompt_data['name'], "tps": tps, "tokens": gen_tokens, "duration": duration, "content": content}
        
    except Exception as e:
        print(f"[!] Error during benchmark: {e}")
        return None

if __name__ == "__main__":
    print("=== APOLLO BENCHMARK: Nemotron-Cascade-14B ===")
    server_process = spin_up_server()
    time.sleep(2) # Give it a moment
    
    results = []
    try:
        for p in PROMPTS:
            res = run_benchmark(p)
            if res: results.append(res)
    finally:
        print("\n[*] Shutting down llama-server...")
        server_process.terminate()
        server_process.wait()
    
    if results:
        print("\n=== BENCHMARK SUMMARY ===")
        avg_tps = sum(r['tps'] for r in results) / len(results)
        print(f"Average Speed: {avg_tps:.2f} tokens/sec")
