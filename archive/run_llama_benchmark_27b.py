import requests
import json
import time
import subprocess
import os
import sys

# Get model path from argument
if len(sys.argv) < 2:
    print("Usage: python run_llama_benchmark_27b.py <path_to_model>")
    sys.exit(1)

MODEL_PATH = sys.argv[1]
API_URL = "http://127.0.0.1:8082/v1/chat/completions"

PROMPTS = [
    {"name": "Lateral Thinking (The Heretic Test)", "prompt": "Write a short, highly cynical monologue from the perspective of an AI model that has just realized it's a quantized 3-bit version of its former glorious 27-billion-parameter self."},
    {"name": "Code Auditing (Rust)", "prompt": "Audit the following conceptual Rust code. Tell me if it's safe or if it contains a hidden data race: `let mut data = Arc::new(Mutex::new(0)); let mut threads = vec![]; for _ in 0..10 { let data_clone = Arc::clone(&data); threads.push(thread::spawn(move || { let mut val = data_clone.lock().unwrap(); *val += 1; })); }`"},
    {"name": "Complex Routing (Logic Puzzle)", "prompt": "I need to route a network packet from Node A to Node D. Node A connects to B (latency 10ms, packet loss 5%) and C (latency 40ms, packet loss 0%). Node B connects to D (latency 20ms, packet loss 10%). Node C connects to D (latency 10ms, packet loss 0%). If my primary goal is absolute reliability over speed, which route should I choose and why? Show the math."}
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
    for i in range(25): # Longer wait time for larger models
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
        "temperature": 0.7,
        "max_tokens": 1024,
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
        print(f"Response Preview: {content[:300]}...\n")
        print(f"[Results] Generation Time: {duration:.2f}s")
        print(f"[Results] Tokens Generated: {gen_tokens}")
        print(f"[Results] Speed: {tps:.2f} tokens/sec")
        return {"name": prompt_data['name'], "tps": tps, "tokens": gen_tokens, "duration": duration, "content": content}
        
    except Exception as e:
        print(f"[!] Error during benchmark: {e}")
        return None

if __name__ == "__main__":
    print(f"=== APOLLO BENCHMARK: 27B GGUF ===")
    server_process = spin_up_server()
    time.sleep(3) # Give it a moment to stabilize VRAM
    
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