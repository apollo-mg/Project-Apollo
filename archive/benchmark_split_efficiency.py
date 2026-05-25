import requests
import json
import time
import sys
import subprocess

# Configuration
GOLD_ZONE_MB = 16000  # 16GB VRAM threshold
BASE_URL = "http://127.0.0.1:11434"
MODEL_LIST = ["deepseek-r1:14b", "qwen3-coder:30b", "qwen3-coder-next"] # Example models
PROMPT = "Write a complete OnShape FeatureScript function that generates a parametric hexagonal bolt."

def get_vram_usage():
    """Simulated or real VRAM usage check."""
    # In a real environment, we'd use the existing vram_management.py logic
    # For this implementation, we assume the environment is set up.
    try:
        import vram_management
        stats = vram_management.get_gpu_stats()
        return stats.get("vram_used_mb", 0)
    except ImportError:
        return 0

def calculate_split_efficiency(model_name, decode_tps, peak_vra_mb):
    """
    Calculates the Split-Efficiency Profile.
    Intelligence-per-Second (IPS) is modeled as decode_tps.
    We weight this by how much of the model resides in the Gold Zone.
    """
    # Penalty factor: 1.0 if in Gold Zone, decays as it enters RAM Penalty Zone
    if peak_vra_mb <= GOLD_ZONE_MB:
        efficiency_multiplier = 1.0
    else:
        # Simple decay: 1.0 at 16GB, 0.5 at 32GB (arbitrary for demonstration)
        efficiency_multiplier = max(0.1, 1.0 - (peak_vra_mb - GOLD_ZONE_MB) / GOLD_ZONE_MB)
    
    ips_adjusted = decode_tps * efficiency_multiplier
    return efficiency_multiplier, ips_adjusted

def run_split_efficiency_benchmark():
    print("--- 🧠 STARTING SPLIT-EFFICIENCY AUDIT ---")
    print(f"Target Gold Zone: {GOLD_ZONE_MB} MB\n")
    
    results = []
    
    for model in MODEL_LIST:
        print(f"Testing: {model}...")
        
        # 1. Setup Payload
        payload = {
            "model": model,
            "prompt": PROMPT,
            "stream": False,
            "options": {"num_predict": 512, "temperature": 0.2}
        }
        
        try:
            start_time = time.time()
            response = requests.post(f"{BASE_URL}/api/generate", json=payload, timeout=120)
            response.raise_for_status()
            data = response.json()
            total_time = time.time() - start_time
            
            # 2. Extract Performance
            eval_count = data.get('eval_count', 0)
            eval_ns = data.get('eval_duration', 1)
            decode_tps = (eval_count / eval_ns) * 1e9
            
            # 3. Extract Memory (Simulated/Real)
            # In a real run, we'd sample peak VRAM during the request
            # For this script, we'll assume the peak is captured via the response or a sidecar
            peak_vra_mb = get_vram_usage() # This is a simplification
            
            # 4. Calculate Profile
            multiplier, ips_adj = calculate_split_efficiency(model, decode_tps, peak_vra_mb)
            
            results.append({
                "model": model,
                "decode_tps": decode_tps,
                "peak_vra_mb": peak_vra_mb,
                "efficiency_multiplier": multiplier,
                "ips_adjusted": ips_adj
            })
            
        except Exception as e:
            print(f"❌ Failed {model}: {e}")

    # 5. Final Report
    print("\n--- 📊 SPLIT-EFFICIENCY HIERARCHY ---")
    print(f"{'Model':<20} | {'t/s':>8} | {'Peak MB':>8} | {'Mult':>6} | {'IPS-Adj':>8}")
    print("-" * 65)
    
    # Sort by Adjusted IPS (Intelligence-per-Second)
    sorted_results = sorted(results, key=lambda x: x['ips_adjusted'], reverse=True)
    
    for r in sorted_results:
        print(f"{r['model']:<20} | {r['decode_tps']:>8.2f} | {r['peak_vra_mb']:>8.0f} | {r['efficiency_multiplier']:>6.2f} | {r['ips_adjusted']:>8.2f}")

if __name__ == "__main__":
    run_split_efficiency_benchmark()