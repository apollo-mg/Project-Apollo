import subprocess
import time
import requests
import json
import sys
from openai import OpenAI
sys.path.append("/home/mark/gemini/")
import vram_management
from llm_interface import nuclear_unload

def test_vllm():
    print("--- [1] PURGING OLLAMA MODELS ---")
    nuclear_unload("qwen3-vl:8b")
    nuclear_unload("qwen3:8b")
    nuclear_unload("deepseek-r1:14b")
    
    print("\n--- [2] WAITING FOR VRAM TO CLEAR ---")
    if not vram_management.wait_for_vram_release(12000, timeout_sec=60):
        print("[ERROR] VRAM did not clear. Cannot safely launch vLLM.")
        return

    print("\n--- [3] LAUNCHING VLLM SERVER (DOCKER / FP8) ---")
    vllm_cmd = [
        "sudo", "docker", "run", "--rm",
        "--name", "vllm-apollo-test",
        "--network=host",
        "--ipc=host",
        "--device=/dev/kfd", "--device=/dev/dri",
        "--privileged",
        "-e", "GCN_ARCH_NAME=gfx1201",
        "-e", "HSA_OVERRIDE_GFX_VERSION=12.0.1",
        "-e", "VLLM_ROCM_USE_AITER=1",
        "-v", "/home/mark/.cache/huggingface:/root/.cache/huggingface",
        "rocm/vllm-dev:rocm7.2_navi_ubuntu24.04_py3.12_pytorch_2.9_vllm_0.14.0rc0",
        "python3", "-m", "vllm.entrypoints.openai.api_server",
        "--model", "neuralmagic/Qwen2.5-Coder-7B-Instruct-FP8-Dynamic",
        "--max-model-len", "8192",
        "--gpu-memory-utilization", "0.60", 
        "--dtype", "bfloat16",
        "--port", "8000"
    ]
    
    server_process = subprocess.Popen(vllm_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    
    # Wait for server to be ready
    server_ready = False
    start_wait = time.time()
    while time.time() - start_wait < 300: # Give it up to 5 mins to download weights the first time
        try:
            res = requests.get("http://127.0.0.1:8000/v1/models", timeout=2)
            if res.status_code == 200:
                server_ready = True
                break
        except:
            time.sleep(2)
            print("Waiting for vLLM to boot...")

    if not server_ready:
        print("[ERROR] vLLM server failed to start.")
        server_process.kill()
        return

    print("\n--- [4] TESTING GUIDED DECODING ---")
    try:
        client = OpenAI(
            base_url="http://127.0.0.1:8000/v1",
            api_key="sk-no-key-required"
        )
        
        schema = {
            "type": "object",
            "properties": {
                "hardware_identified": {"type": "string"},
                "confidence_score": {"type": "number"},
                "requires_further_search": {"type": "boolean"}
            },
            "required": ["hardware_identified", "confidence_score", "requires_further_search"]
        }

        response = client.chat.completions.create(
            model="neuralmagic/Qwen2.5-Coder-7B-Instruct-FP8-Dynamic",
            messages=[
                {"role": "system", "content": "You are a hardware expert."},
                {"role": "user", "content": "I am looking at a green circuit board with 'Raspberry Pi 4 Model B' written on the silkscreen."}
            ],
            extra_body={"guided_json": schema},
            temperature=0.0
        )
        
        print("\n[SUCCESS] Guided JSON Output:")
        print(response.choices[0].message.content)
        
    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        
    finally:
        print("\n--- [5] TEARDOWN: KILLING VLLM DOCKER CONTAINER ---")
        subprocess.run(["sudo", "docker", "stop", "vllm-apollo-test"], capture_output=True)
        server_process.terminate()
        server_process.wait()
        print("vLLM shutdown complete. VRAM returning to baseline.")

if __name__ == "__main__":
    test_vllm()