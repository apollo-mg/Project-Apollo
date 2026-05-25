import requests
import json
import time
import os
import subprocess
from llm_interface import nuclear_unload, query_llm, ENGINEER_MODEL, ARCHITECT_MODEL, VISION_MODEL
import vram_management

# Configuration
MODELS = ["deepseek-r1:14b", "qwen3-coder:30b", "qwen3-coder-next"]
BASE_URL = "http://127.0.0.1:11434"
PROMPT = "Write a complete OnShape FeatureScript function that generates a parametric hexagonal bolt. It should include parameters for head_diameter, bolt_length, and thread_pitch. Use opBox for the head and opCylinder for the shaft. Include necessary imports."

def get_vram():
    stats = vram_management.get_gpu_stats()
    return stats.get("vram_used_mb", 0)

def run_benchmark(model_name):
    print(f"\n--- BENCHMARKING: {model_name} ---")
    
    # 1. Nuclear unload others
    for m in MODELS:
        nuclear_unload(m)
    nuclear_unload("qwen2.5vl:latest")
    time.sleep(5)
    
    start_vram = get_vram()
    print(f"Initial VRAM: {start_vram:.0f} MB")
    
    payload = {
        "model": model_name,
        "prompt": PROMPT,
        "stream": False,
        "options": {
            "num_predict": 1024,
            "temperature": 0.2
        }
    }
    
    try:
        start_time = time.time()
        response = requests.post(f"{BASE_URL}/api/generate", json=payload, timeout=900)
        response.raise_for_status()
        data = response.json()
        total_time = time.time() - start_time
        
        peak_vram = get_vram()
        
        p_eval_count = data.get('prompt_eval_count', 0)
        p_eval_ns = data.get('prompt_eval_duration', 1)
        eval_count = data.get('eval_count', 0)
        eval_ns = data.get('eval_duration', 1)
        
        prefill_tps = (p_eval_count / p_eval_ns) * 1e9
        decode_tps = (eval_count / eval_ns) * 1e9
        
        print(f"Decode: {decode_tps:.2f} t/s | Peak VRAM: {peak_vram:.0f} MB")
        
        return {
            "model": model_name,
            "decode_tps": decode_tps,
            "vram_peak_mb": peak_vram,
            "response": data.get('response', '')
        }
        
    except Exception as e:
        print(f"Error: {e}")
        return None

def main():
    results = []
    for model in MODELS:
        res = run_benchmark(model)
        if res: results.append(res)
    
    print("\n--- SUMMARY ---")
    for r in results:
        print(f"{r['model']:<20} | {r['decode_tps']:>10.2f} t/s | {r['vram_peak_mb']:>8.0f} MB")

if __name__ == "__main__":
    main()
