import time
import subprocess
import json
import os
import requests
from modules.theme import stylized_print, CLR_GOLD, CLR_CYAN, CLR_BLUE

def get_vram_usage():
    try:
        res = subprocess.check_output(["rocm-smi", "--showmeminfo", "vram", "--json"])
        data = json.loads(res)
        # Adjusting for potential rocm-smi json structure differences in 7.2
        gpu_0 = data.get("card0", data.get("0", {}))
        used = int(gpu_0.get("VRAM Total Used", 0)) / 1024 / 1024
        return used
    except:
        return 0

def stress_test_model(model_name, prompt, iterations=1):
    stylized_print("STRESS", f"Loading {model_name}...", color=CLR_CYAN)
    start_vram = get_vram_usage()
    
    for i in range(iterations):
        stylized_print("TEST", f"Iteration {i+1}/{iterations} for {model_name}", color=CLR_BLUE)
        start_time = time.time()
        try:
            resp = requests.post("http://127.0.0.1:11434/api/generate", 
                               json={"model": model_name, "prompt": prompt, "stream": False},
                               timeout=300)
            duration = time.time() - start_time
            if resp.status_code == 200:
                tps = resp.json().get("eval_count", 0) / (resp.json().get("eval_duration", 1) / 1e9)
                stylized_print("RESULT", f"{model_name}: {tps:.2f} t/s | Time: {duration:.2f}s", color=CLR_GOLD)
            else:
                stylized_print("ERROR", f"Status {resp.status_code}: {resp.text}", color=CLR_GOLD)
        except Exception as e:
            stylized_print("CRITICAL", f"Test failed: {e}", color=CLR_GOLD)
    
    end_vram = get_vram_usage()
    stylized_print("VRAM", f"Used: {end_vram:.2f}MB (Delta: {end_vram - start_vram:.2f}MB)", color=CLR_CYAN)

if __name__ == "__main__":
    print("--- 🛡️ PROJECT APOLLO: THE GAUNTLET (ROCM 7.2 STRESS TEST) ---")
    
    # Test 1: High-Speed Engineer (14B)
    stress_test_model("deepseek-r1:14b", "Explain the architectural differences between RDNA 3 and RDNA 4 in extreme detail, focusing on the changes to the dual-issue stream processors and AI accelerators.")
    
    # Test 2: The VRAM Edge (30B Architect)
    # We use a massive prompt to fill the KV cache
    long_prompt = "Write a complete, production-ready Rust backend for a distributed sensor network. Include async trait implementations, custom error types, and a CLI interface using 'clap'. " * 10
    stress_test_model("qwen3-coder:30b", long_prompt)
    
    # Test 3: Vision Check
    stress_test_model("qwen2.5vl:latest", "Describe the theoretical hardware layout of an RX 9070 XT based on its GFX1201 identifier.")
    
    print("\n--- ✅ GAUNTLET COMPLETE ---")
