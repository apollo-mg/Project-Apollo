import time
import json
import requests
import os

# Configuration for Crow-9B HERETIC served on port 8082
API_URL = "http://127.0.0.1:8082/v1/chat/completions"
MODEL_NAME = "Crow-9B-HERETIC-4.6.i1-Q6_K.gguf"

def run_benchmark(prompt, max_tokens=256):
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": "You are a highly capable terminal agent. Use a concise, senior engineer tone."},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": max_tokens,
        "temperature": 0.0,
        "stream": False
    }

    print(f"--- Benchmarking Crow-9B: {prompt[:40]}... ---")
    start_time = time.time()
    try:
        response = requests.post(API_URL, json=payload, timeout=60)
        response.raise_for_status()
        end_time = time.time()
        
        data = response.json()
        content = data['choices'][0]['message']['content']
        usage = data.get('usage', {})
        
        latency = end_time - start_time
        tps = usage.get('completion_tokens', 0) / latency if latency > 0 else 0
        
        print(f"Latency: {latency:.2f}s")
        print(f"Tokens/Sec: {tps:.2f}")
        print(f"Response: {content[:100]}...")
        return True
    except Exception as e:
        print(f"Benchmark Failed: {e}")
        return False

if __name__ == "__main__":
    # Test 1: Reasoning (Water Jug logic check)
    run_benchmark("Explain why a 6L jug is sufficient to measure 6L in one step.")
    
    # Test 2: Code Generation
    run_benchmark("Write a Python decorator called @require_approval that uses kdialog to ask 'Proceed?'.")
