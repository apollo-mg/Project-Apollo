import sys
import json
import random
import time
import requests
import subprocess
import os
import vram_management

COMFY_URL = "http://127.0.0.1:8189"
WORKFLOW_FILE = "/home/mark/gemini/ai/flux_workflow.json"
START_SCRIPT = "/home/mark/gemini/ai/run_comfy_final.sh"
OUTPUT_DIR = "/home/mark/gemini/ai/output/voice_gen"

def check_server():
    try:
        requests.get(f"{COMFY_URL}/system_stats", timeout=1)
        return True
    except:
        return False

def start_server():
    if check_server():
        return

    print("Starting ComfyUI...")
    # Run in background detached
    subprocess.Popen(f"nohup {START_SCRIPT} > /dev/null 2>&1 &", shell=True)
    
    for i in range(120): # Increased timeout for slow startup
        if check_server():
            print("ComfyUI is ready!")
            time.sleep(5)
            return
        time.sleep(1)
        print(".", end="", flush=True)
    
    print("\nFailed to start ComfyUI.")
    sys.exit(1)

def generate(prompt):
    # Check if we need space before starting ComfyUI
    vram_management.smart_vram_guard()
    start_server()
    
    try:
        with open(WORKFLOW_FILE, 'r') as f:
            workflow = json.load(f)
    except FileNotFoundError:
        print(f"Workflow file not found: {WORKFLOW_FILE}")
        return

    # Update Prompt (Node 6)
    try:
        workflow["6"]["inputs"]["text"] = prompt
    except KeyError:
        print("Error: Workflow JSON structure mismatch (Node 6 text input not found)")
        return
    
    # Random Seed (Node 25)
    seed = random.randint(1, 1000000000000000)
    try:
        workflow["25"]["inputs"]["noise_seed"] = seed
    except KeyError:
        print("Warning: Seed node 25 not found, using default seed.")
    
    # Queue Prompt
    p = {"prompt": workflow}
    try:
        res = requests.post(f"{COMFY_URL}/prompt", json=p)
        res.raise_for_status()
        prompt_id = res.json().get('prompt_id')
        print(f"Queued Prompt ID: {prompt_id}")
    except Exception as e:
        print(f"Error queuing prompt: {e}")
        return

    # Wait for completion
    print("Generating...")
    start_time = time.time()
    while time.time() - start_time < 600: # 10 min timeout (Flux is slow on CPU if fallback)
        try:
            hist = requests.get(f"{COMFY_URL}/history/{prompt_id}").json()
            if prompt_id in hist:
                outputs = hist[prompt_id]['outputs']
                # Iterate outputs to find images
                for node_id in outputs:
                    if 'images' in outputs[node_id]:
                        for img in outputs[node_id]['images']:
                            fname = img['filename']
                            subfolder = img['subfolder']
                            folder_type = img['type']
                            
                            # Download
                            img_url = f"{COMFY_URL}/view?filename={fname}&subfolder={subfolder}&type={folder_type}"
                            img_data = requests.get(img_url).content
                            
                            os.makedirs(OUTPUT_DIR, exist_ok=True)
                            out_path = os.path.join(OUTPUT_DIR, f"flux_{seed}.png")
                            with open(out_path, 'wb') as f:
                                f.write(img_data)
                            print(f"Image Saved: {out_path}")
                            sound_path = os.path.join(os.getcwd(), "sounds", "ready.wav")
                            if os.path.exists(sound_path):
                                subprocess.run(["aplay", "-q", sound_path])
                            
                            # Clean up VRAM after generation
                            vram_management.unload_comfy_vram()
                            return out_path
                break
        except Exception as e:
            pass
        time.sleep(1)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python generate_image.py <prompt>")
        sys.exit(1)
    
    generate(sys.argv[1])
