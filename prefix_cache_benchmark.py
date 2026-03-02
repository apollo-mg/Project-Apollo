import time
import requests
import json

# Target Ollama API
OLLAMA_API = "http://localhost:11434/api/chat"
MODEL = "deepseek-r1:14b"

# Simulated 2000-token System Prompt
SYSTEM_PROMPT = "PROJECT JARVIS TECHNICAL CONTEXT: " + "DEBUGGING ROCM 7.1 ON RDNA 4. " * 250

def get_ttft(user_input):
    start_time = time.time()
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_input}
        ],
        "stream": True,
        "keep_alive": -1  # Keep model in memory indefinitely
    }

    try:
        with requests.post(OLLAMA_API, json=payload, stream=True, timeout=60) as r:
            r.raise_for_status()
            for line in r.iter_lines():
                if line:
                    body = json.loads(line)
                    # Return time on the very first token received
                    if not body.get("done"):
                        return time.time() - start_time
    except Exception as e:
        print(f"Error: {e}")
    return None

print("--- OLLAMA RESIDENT CACHE BENCHMARK ---")
print(f"Target: {MODEL} on Native ROCm 7.1.1 (RX 9070 XT)")
print("-" * 50)

# Pre-load the model to ensure TTFT doesn't include the 9GB model load time
print(f"Pre-loading {MODEL} into VRAM...")
requests.post(OLLAMA_API, json={"model": MODEL, "messages": [], "keep_alive": -1})
time.sleep(2) # Give it a moment to settle

print("\n[TEST 1: Cold Cache (Prefill Phase)]")
print("Sending 2,000 token context + query...")
ttft_cold = get_ttft("Jarvis, check the thermal state of the VzBoT gantry.")

if ttft_cold:
    print(f"Cold TTFT: {ttft_cold:.4f} seconds")
    
    print("\n[TEST 2: Hot Cache (Prefix Hit)]")
    print("Sending identical 2,000 token context + new query...")
    # Wait a second so we can distinctly see the second request in logs if needed
    time.sleep(1) 
    ttft_hot = get_ttft("Jarvis, cross-reference that with the linear rail specs.")
    
    if ttft_hot:
        print(f"Hot TTFT: {ttft_hot:.4f} seconds")
        
        reduction = (1 - (ttft_hot / ttft_cold)) * 100
        print("-" * 50)
        print(f"LATENCY REDUCTION: {reduction:.2f}%")
        
        if reduction > 70:
            print("STATUS: ✅ SUCCESS. Prefix caching is highly effective in Ollama.")
        elif reduction > 0:
            print("STATUS: ⚠️ MODERATE. Caching works but is not hitting the 70% target.")
        else:
            print("STATUS: ❌ FAILED. Caching is not active or TTFT worsened.")
    else:
        print("Test 2 failed.")
else:
    print("Test 1 failed.")
