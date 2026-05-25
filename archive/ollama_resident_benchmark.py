import time
import requests
import json
import subprocess

# Settings
OLLAMA_API = "http://127.0.0.1:11434/api"
ENGINEER = "deepseek-r1:14b"
RECEPTIONIST = "llama3.2:1b"

def get_vram():
    try:
        res = subprocess.run(["rocm-smi", "--showmeminfo", "vram", "--json"], capture_output=True, text=True)
        data = json.loads(res.stdout)
        return int(data["card0"]["VRAM Total Used Memory (B)"]) / (1024**2)
    except: return 0

def unload_all():
    print("--> FORCE UNLOADING ALL MODELS...")
    try:
        requests.post(f"{OLLAMA_API}/chat", json={"model": RECEPTIONIST, "keep_alive": 0})
        requests.post(f"{OLLAMA_API}/chat", json={"model": ENGINEER, "keep_alive": 0})
    except: pass
    time.sleep(2)

def query(model, text, keep_alive=None, context_size=None):
    start = time.time()
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": text}],
        "stream": False
    }
    if keep_alive is not None:
        payload["keep_alive"] = keep_alive
        
    # FORCE SMALLER CONTEXT FOR ENGINEER TO FIT
    if context_size:
        payload["options"] = {"num_ctx": context_size}
        
    print(f"--> Requesting {model} (ctx={context_size if context_size else 'default'})...")
    try:
        requests.post(f"{OLLAMA_API}/chat", json=payload, timeout=300)
    except Exception as e:
        print(f"Query Failed: {e}")
    return time.time() - start

print("--- JARVIS LATENCY AUDIT: TIGHT FIT MODE ---")
unload_all()
print(f"Starting VRAM: {get_vram():.0f}MB")

# 1. Load Receptionist Resident
print("\n[STEP 1] Loading Receptionist (Resident)...")
t_init = query(RECEPTIONIST, "Hello", keep_alive=-1, context_size=2048) 
print(f"Receptionist Ready in {t_init:.2f}s")
print(f"VRAM: {get_vram():.0f}MB")

# 2. Load Engineer (WITH REDUCED CONTEXT)
print("\n[STEP 2] Loading Engineer (DeepSeek-R1 14B)...")
t_load_eng = query(ENGINEER, "Search the vault for Octopus Pro pinout.", keep_alive="5m", context_size=2048)
print(f"Engineer Load + Response: {t_load_eng:.2f}s")
print(f"VRAM: {get_vram():.0f}MB")

# 3. Switch back to Receptionist
print("\n[STEP 3] Switching back to Receptionist...")
t_persona = query(RECEPTIONIST, "Translate this technical data.", keep_alive=-1)
print(f"Persona Pass in {t_persona:.2f}s")
print(f"VRAM: {get_vram():.0f}MB")

print("-" * 40)
print("TEST COMPLETE")
