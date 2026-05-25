#!/usr/bin/env python3
import subprocess
import time
import os
import signal

MODELS = {
    "architect": "/media/mark/AI_Fast/models/Apollo-Architect-35B-Sovereign-IQ2_M.gguf",
    "architect_lean": "/media/mark/AI_Fast/Models/GGUF/Apollo-35B-Sovereign-Architect.iq2_xxs.gguf",
    "tesslate": "/media/mark/AI_Fast/Models/GGUF/Tesslate_OmniCoder-9B-Q6_K.gguf",
    "engineer": "/media/mark/AI_Fast/Models/GGUF/Qwen2.5-Coder-14B-Instruct-Q6_K.gguf",
    "heretic": "/media/mark/TG_2TB/Models/GGUF/Qwen3.5-9B-Claude-4.6-HighIQ-THINKING-HERETIC-UNCENSORED.i1-Q5_K_M.gguf"
}

LLAMA_SERVER_BIN = "/home/mark/llama.cpp/build/bin/llama-server"
PORT = 11435

def kill_existing():
    print(f"[*] Stopping any existing server on port {PORT}...")
    try:
        # Find process using the port
        result = subprocess.check_output(["lsof", "-t", f"-i:{PORT}"])
        pids = result.decode().strip().split('\n')
        for pid in pids:
            if pid.strip():
                os.kill(int(pid), signal.SIGTERM)
        time.sleep(2)
    except:
        pass

def load_model(name):
    if name not in MODELS:
        print(f"Error: Unknown model '{name}'")
        return

    path = MODELS[name]
    kill_existing()
    
    print(f"[+] Loading {name} into VRAM...")
    
    env = os.environ.copy()
    env["HSA_ENABLE_SDMA"] = "0"
    env["AMDGPU_CWSR_ENABLE"] = "0"
    env["HSA_OVERRIDE_GFX_VERSION"] = "12.0.1"
    
    cmd = [
        LLAMA_SERVER_BIN,
        "-m", path,
        "--port", str(PORT),
        "--host", "0.0.0.0", "--mmproj", "/media/mark/AI_Fast/Models/GGUF/qwen3.5-35b-mmproj-f16.gguf", "-c", "32768", "--chat-template-kwargs", "{\"enable_thinking\":false}",
        "-ngl", "99",
        "-fa", "on",
        "-ub", "1024",
        "-b", "1024"
    ]
    
    subprocess.Popen(cmd, env=env, stdout=open("/home/mark/gemini/llama_server.log", "a"), stderr=subprocess.STDOUT)
    print(f"[!] {name} is now warming up on port {PORT}.")

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: forge_manager.py [load <model_name> | kill]")
    elif sys.argv[1] == "kill":
        kill_existing()
        print("[!] VRAM Cleared.")
    elif sys.argv[1] == "load" and len(sys.argv) >= 3:
        load_model(sys.argv[2])
    else:
        print("Invalid command.")
