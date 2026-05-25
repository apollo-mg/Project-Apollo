import subprocess
import requests
import time
import json
import os

SERVER_BIN = "/mnt/TG_2TB/Projects/Apollo/engines/llama_cpp_gemma4/build/bin/llama-server"
MODELS = {
    "Gemma-4-31B-Dense": "/mnt/TG_2TB/AI/Models/Gemma 4/gemma-4-31B-it-UD-IQ2_XXS.gguf",
    "Gemma-4-E4B-Dense": "/mnt/TG_2TB/AI/Models/Gemma 4/gemma-4-E4B-it-UD-IQ3_XXS.gguf",
    "Gemma-4-E2B-Dense": "/mnt/TG_2TB/AI/Models/Gemma 4/gemma-4-E2B-it-UD-Q4_K_XL.gguf"
}

PROMPTS = {
    "1_Coding": "Write a robust Python script to implement an asyncio-based worker pool that processes tasks from a queue with a maximum concurrency of 5. Include proper error handling, logging, and graceful shutdown on SIGINT. Reply only with the code.",
    "2_Logic": "Three friends check into a hotel room that costs $30. They each contribute $10. Later, the manager realizes the room only costs $25 and gives the bellboy $5 to return to them. The bellboy keeps $2 and gives $1 to each friend. Now, each friend has paid $9 (total $27), and the bellboy has $2. $27 + $2 = $29. Where is the missing dollar? Explain clearly.",
    "3_Constraints": "Explain the concept of entropy. You must use exactly 3 sentences. Every sentence must start with the letter 'E'.",
    "4_Architecture": "Propose a high-level system architecture for a distributed local-first AI system that synchronizes semantic memory across peers using ChromaDB and a CRDT-based consensus approach. Keep it concise but deeply technical."
}

ENV = os.environ.copy()
ENV["HSA_OVERRIDE_GFX_VERSION"] = "12.0.1"
ENV["GGML_HIP_FORCE_MMQ"] = "1"
ENV["HSA_ENABLE_SDMA"] = "0"
ENV["AMDGPU_CWSR_ENABLE"] = "0"
ENV["HSA_XNACK"] = "0"

def wait_for_server(port=8085, timeout=120):
    start = time.time()
    while time.time() - start < timeout:
        try:
            res = requests.get(f"http://127.0.0.1:{port}/health", timeout=2)
            if res.status_code == 200:
                time.sleep(2)
                return True
        except:
            time.sleep(2)
    return False

results = {}

for model_name, model_path in MODELS.items():
    print(f"\n[{model_name}] Starting server...")
    
    cmd = [
        SERVER_BIN, "-m", model_path, "-c", "4096", "-b", "512", "-ub", "128",
        "-ctk", "q4_0", "-ctv", "q4_0", "-cb", "-fa", "on", "-np", "1", "-ngl", "99",
        "--cache-ram", "0", "--no-cache-prompt", "--port", "8085", "--host", "127.0.0.1"
    ]
    
    process = subprocess.Popen(cmd, env=ENV, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    if not wait_for_server():
        print(f"[{model_name}] Server failed to start.")
        process.kill()
        continue
        
    print(f"[{model_name}] Server ready. Running benchmarks...")
    results[model_name] = {}
    
    for test_name, prompt in PROMPTS.items():
        print(f"  -> Running {test_name}...")
        payload = {
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "max_tokens": 1024
        }
        
        t0 = time.time()
        try:
            res = requests.post("http://127.0.0.1:8085/v1/chat/completions", json=payload, timeout=300)
            t1 = time.time()
            data = res.json()
            if "choices" in data and len(data["choices"]) > 0:
                reply = data["choices"][0]["message"]["content"]
                tokens = data["usage"]["completion_tokens"]
                tps = tokens / (t1 - t0)
                
                results[model_name][test_name] = {
                    "time_sec": round(t1 - t0, 2),
                    "tps": round(tps, 2),
                    "reply": reply
                }
            else:
                print(f"  -> Unexpected response: {data}")
                results[model_name][test_name] = {"error": "Unexpected response", "raw": data}
        except Exception as e:
            print(f"  -> Error: {e}")
            results[model_name][test_name] = {"error": str(e)}
            
    print(f"[{model_name}] Shutting down server...")
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
    time.sleep(3)

with open("/mnt/TG_2TB/Projects/Apollo/moe_shootout_results.json", "w") as f:
    json.dump(results, f, indent=2)

print("\nBenchmark complete. Results saved to moe_shootout_results.json")