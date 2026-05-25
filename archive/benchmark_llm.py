import requests
import json
import time
import sys
import vram_management

# Configuration
MODEL = "deepseek-r1:14b"
BASE_URL = "http://127.0.0.1:11434"
PROMPT = "Explain the difference between a mutex and a semaphore in Rust, providing a short code example for each."

def check_service():
    """Verifies Ollama service health and model availability."""
    print(f"--- 🔍 DIAGNOSTICS ---")
    
    # SAFETY CHECK
    print("--- 🛡️ VRAM SAFETY CHECK ---")
    used_vram = vram_management.get_vram_usage()
    if used_vram > 4000: # If more than 4GB used, unsafe to load 14B model
        print(f"❌ VRAM BUSY ({used_vram:.0f}MB). Unload other models first!")
        return False
    print(f"✅ VRAM OK ({used_vram:.0f}MB used)")

    try:
        # Check Version
        ver_resp = requests.get(f"{BASE_URL}/api/version", timeout=2)
        if ver_resp.status_code == 200:
            version = ver_resp.json().get('version', 'Unknown')
            print(f"✅ Service Online: Ollama v{version}")
        else:
            print(f"❌ Service Error: HTTP {ver_resp.status_code}")
            return False

        # Check Models
        tags_resp = requests.get(f"{BASE_URL}/api/tags", timeout=2)
        if tags_resp.status_code == 200:
            models = [m['name'] for m in tags_resp.json().get('models', [])]
            if not models:
                print("❌ NO MODELS FOUND! The service is running but has no models loaded.")
                print("   Check if OLLAMA_MODELS environment variable points to the correct directory.")
                return False
            
            print(f"✅ Found {len(models)} models: {', '.join(models[:3])}...")
            
            # Check for specific model
            # Note: Model names can have tags like :latest or :14b
            if not any(MODEL in m for m in models):
                print(f"⚠️  WARNING: Requested model '{MODEL}' not found in list.")
                print(f"   Available: {models}")
                # Try to use first available model as fallback?
                fallback = models[0]
                print(f"   Using fallback model: {fallback}")
                return fallback
            return MODEL
        else:
            print(f"❌ Failed to list models: HTTP {tags_resp.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print(f"❌ CONNECTION FAILED: Is Ollama running at {BASE_URL}?")
        return False
    except Exception as e:
        print(f"❌ Diagnostic Error: {e}")
        return False

def run_benchmark(model_name):
    print(f"\n--- 🧠 BENCHMARKING: {model_name} ---")
    print(f"Prompting: '{PROMPT}'")
    
    # Payload for native generate endpoint
    payload = {
        "model": model_name,
        "prompt": PROMPT,
        "stream": False,
        "options": {
            "num_predict": 512, # Limit generation for consistency
            "temperature": 0.7
        }
    }
    
    start_time = time.time()
    try:
        # Using /api/generate for detailed timing stats
        response = requests.post(f"{BASE_URL}/api/generate", json=payload, timeout=120)
        
        if response.status_code == 404:
            print("❌ Endpoint /api/generate not found. Using OpenAI fallback...")
            # Fallback code if needed, but for now just fail if native API missing
            return

        response.raise_for_status()
        data = response.json()
        total_time = time.time() - start_time
        
        # Extract Metrics (Ollama returns nanoseconds)
        load_ns = data.get('load_duration', 0)
        prompt_eval_count = data.get('prompt_eval_count', 0)
        prompt_eval_ns = data.get('prompt_eval_duration', 0)
        eval_count = data.get('eval_count', 0)
        eval_ns = data.get('eval_duration', 0)
        
        # Convert to ms and rates
        load_ms = load_ns / 1e6
        
        prefill_rate = 0
        if prompt_eval_ns > 0:
            prefill_rate = (prompt_eval_count / prompt_eval_ns) * 1e9
            
        decode_rate = 0
        if eval_ns > 0:
            decode_rate = (eval_count / eval_ns) * 1e9
            
        print("\n--- 📊 PERFORMANCE METRICS ---")
        print(f"Model Load Time:       {load_ms:.2f} ms")
        print(f"Prompt Eval (Prefill): {prefill_rate:.2f} tokens/sec ({prompt_eval_count} tokens)")
        print(f"Response (Decode):     {decode_rate:.2f} tokens/sec ({eval_count} tokens)")
        print(f"Total Latency:         {total_time:.2f} seconds")
        
        response_text = data.get('response', '')
        snippet = response_text[:200].replace('\n', ' ') + "..."
        print(f"\n--- 📝 OUTPUT SNIPPET ---\n{snippet}")
        
    except Exception as e:
        print(f"❌ Benchmark Failed: {e}")

if __name__ == "__main__":
    target_model = check_service()
    if target_model:
        run_benchmark(target_model)
    else:
        sys.exit(1)
