import time
import requests
import json
import os

OLLAMA_API = "http://127.0.0.1:11434/api/chat"
MODEL = "llama3.2:1b"

SYSTEM_PROMPT = """You are the Apollo Dispatcher.
Return ONLY a JSON object for the tool check_gpu if requested.
{"tool": "check_gpu", "args": {}}"""

def benchmark_tool_latency():
    print(f"--- Benchmarking {MODEL} Tool Latency ---")
    
    # 1. Warmup
    print("Warming up...", end="", flush=True)
    try:
        requests.post(OLLAMA_API, json={"model": MODEL, "messages": [{"role": "user", "content": "hi"}], "keep_alive": -1})
    except:
        pass
    print(" Done.")

    latencies = []
    for i in range(5):
        payload = {
            "model": MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": "Check the GPU status please."}
            ],
            "stream": False,
            "options": {"temperature": 0.0}
        }
        
        start = time.time()
        try:
            res = requests.post(OLLAMA_API, json=payload)
            res.raise_for_status()
            data = res.json()
            end = time.time()
            
            latency = (end - start) * 1000
            latencies.append(latency)
            print(f"Iteration {i+1}: {latency:.2f}ms")
        except Exception as e:
            print(f"Iteration {i+1}: ERROR: {e}")

    if latencies:
        avg_latency = sum(latencies) / len(latencies)
        print(f"\nAverage Latency: {avg_latency:.2f}ms")
        print(f"Tool Routing Speed: {1000/avg_latency:.2f} calls/sec")
    else:
        print("\nBenchmark failed: No successful iterations.")

if __name__ == "__main__":
    benchmark_tool_latency()
