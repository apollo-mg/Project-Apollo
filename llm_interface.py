import requests
import json
import sys
import base64
import vram_management
import threading
import subprocess

# Native Ollama API endpoint
LLM_API_URL = "http://127.0.0.1:11434/api/chat"

# Global lock for model swaps to prevent VRAM race conditions/freezes
MODEL_LOCK = threading.Lock()

# --- SEMANTIC MODEL DEFINITIONS (PHASE 6) ---
GATEKEEPER_MODEL = "qwen3:0.6b"           # Resident (System 1) - Triage/Fast-Response
ENGINEER_MODEL = "qwen3:8b"             # Primary Workhorse (System 2) - Logic/Coding
DEEP_ENGINEER_MODEL = "deepseek-r1:14b" # Reasoning Specialist - Deep Logic/CoT
ARCHITECT_MODEL = "qwen3-coder:30b"     # Structural Specialist (System 1.5) - Complex Architecture
RECEPTIONIST_MODEL = "qwen3:0.6b"       # Dedicated Resident Interaction
VISION_MODEL = "qwen3-vl:8b"            # Primary Vision (RDNA 4 Optimized)

MODEL_NAME = ENGINEER_MODEL 
FALLBACK_MODEL = GATEKEEPER_MODEL
TIMEOUT_SEC = 600 # Wait for VRAM swap/flush

from PIL import Image
import io

def encode_image(image_path):
    """Downscales image to max 1280px before encoding to save VRAM."""
    try:
        with Image.open(image_path) as img:
            # Convert to RGB if necessary
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Max dimension 1280px for the "Sweet Spot" on Vulkan
            img.thumbnail((1280, 1280))
            
            buffered = io.BytesIO()
            img.save(buffered, format="JPEG", quality=85)
            return base64.b64encode(buffered.getvalue()).decode('utf-8')
    except Exception as e:
        print(f"Image processing error: {e}")
        # Fallback to original if PIL fails
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')

def nuclear_unload(model_name):
    """Forcefully stops a model via Ollama and waits for VRAM release."""
    try:
        print(f"--- [VRAM: NUCLEAR UNLOAD OF {model_name}] ---")
        subprocess.run(["ollama", "stop", model_name], check=True, capture_output=True)
        # Wait for at least 8GB if it was a big model
        threshold = 8000 if ("qwen" in model_name.lower() or "deepseek-r1:14b" in model_name.lower()) else 2000
        return vram_management.wait_for_vram_release(threshold)
    except Exception as e:
        print(f"Nuclear unload error: {e}")
        return False

def query_llm(prompt, system_message=None, model_override=None, messages_override=None, image_path=None):
    target_model = model_override or MODEL_NAME
    
    with MODEL_LOCK:
        big_models = [ENGINEER_MODEL, DEEP_ENGINEER_MODEL, ARCHITECT_MODEL, VISION_MODEL]
        if target_model in big_models:
            loaded = get_loaded_models()
            is_loaded = any(target_model in m for m in loaded)
            if not is_loaded:
                for bm in big_models:
                    if bm != target_model and any(bm in m for m in loaded):
                        # Unload other big model first
                        if not unload_model(bm):
                             # Try nuclear
                             if not nuclear_unload(bm):
                                 raise RuntimeError(f"CRITICAL VRAM SAFETY: Failed to unload {bm}. Aborting load of {target_model} to prevent driver crash.")

        keep_alive = -1 if target_model == RECEPTIONIST_MODEL else "5m"

        payload = {
            "model": target_model,
            "stream": False,
            "messages": [],
            "keep_alive": keep_alive,
            "options": {"num_ctx": 8192}
        }

    if system_message:
        payload["messages"].append({"role": "system", "content": system_message})

    if messages_override:
        payload["messages"] = list(messages_override) # Copy to avoid mutating original
        if prompt:
            payload["messages"].append({"role": "user", "content": prompt})
    else:
        payload["messages"].append({"role": "user", "content": prompt or "Describe this image in detail."})

    if image_path:
        images_to_attach = []
        if isinstance(image_path, list):
            for path in image_path:
                images_to_attach.append(encode_image(path))
        else:
            images_to_attach.append(encode_image(image_path))
            
        # Attach image to the last user message
        for msg in reversed(payload["messages"]):
            if msg["role"] == "user":
                msg["images"] = images_to_attach
                break

    def attempt_query():
        response = requests.post(LLM_API_URL, json=payload, headers={"Content-Type": "application/json"}, timeout=TIMEOUT_SEC)
        response.raise_for_status()
        content = response.json()['message']['content']
        # Strip DeepSeek-R1 thinking tags
        if "<think>" in content and "</think>" in content:
            content = content.split("</think>")[-1].strip()
        return content

    try:
        return attempt_query()
    except Exception as e:
        return f"Error connecting to LLM: {e}"

def get_loaded_models():
    try:
        response = requests.get(f"http://127.0.0.1:11434/api/ps", timeout=2)
        if response.status_code == 200:
            return [m['name'] for m in response.json().get('models', [])]
    except:
        pass
    return []

def stream_llm(prompt, system_message=None, model_override=None, messages_override=None, image_path=None):
    """
    Generator that streams the LLM response token by token.
    Enables Unified Tool Interception (UTI) by allowing the agent to inspect output in real-time.
    """
    target_model = model_override or MODEL_NAME
    
    with MODEL_LOCK:
        # Check VRAM before loading big models
        big_models = [ENGINEER_MODEL, DEEP_ENGINEER_MODEL, ARCHITECT_MODEL, VISION_MODEL]
        if target_model in big_models:
            loaded = get_loaded_models()
            is_loaded = any(target_model in m for m in loaded)
            
            if not is_loaded:
                for bm in big_models:
                    if bm != target_model and any(bm in m for m in loaded):
                        print(f"--- [VRAM: SWAP DETECTED. Loading {target_model}, Unloading {bm}] ---", flush=True)
                        if not unload_model(bm):
                            if not nuclear_unload(bm):
                                raise RuntimeError(f"CRITICAL VRAM SAFETY: Failed to unload {bm}. Aborting load of {target_model} to prevent driver crash.")

        # Determine keep_alive based on model
        keep_alive = -1 if target_model == RECEPTIONIST_MODEL else "5m"

        payload = {
            "model": target_model,
            "stream": True,
            "messages": [],
            "keep_alive": keep_alive,
            "options": {"num_ctx": 8192}
        }

        if system_message:
            payload["messages"].append({"role": "system", "content": system_message})

        if messages_override:
            payload["messages"] = list(messages_override) # Copy to avoid mutating original
            if prompt:
                payload["messages"].append({"role": "user", "content": prompt})
        else:
            payload["messages"].append({"role": "user", "content": prompt or "Describe this image in detail."})

        if image_path:
            images_to_attach = []
            if isinstance(image_path, list):
                for path in image_path:
                    images_to_attach.append(encode_image(path))
            else:
                images_to_attach.append(encode_image(image_path))
                
            # Attach image to the last user message
            for msg in reversed(payload["messages"]):
                if msg["role"] == "user":
                    msg["images"] = images_to_attach
                    break

        try:
            with requests.post(LLM_API_URL, json=payload, stream=True, timeout=TIMEOUT_SEC) as r:
                r.raise_for_status()
                for line in r.iter_lines():
                    if line:
                        body = json.loads(line)
                        if "error" in body:
                            raise Exception(body["error"])
                        if body.get("done") is False:
                            content = body.get("message", {}).get("content", "")
                            yield content
        except Exception as e:
            yield f"Error connecting to LLM: {e}"

def unload_model(model_name):
    """
    Verified unload: Block until VRAM is actually free.
    """
    if model_name == RECEPTIONIST_MODEL:
        return True # We NEVER unload the resident receptionist

    try:
        # Check current VRAM usage
        used_before = vram_management.get_vram_usage()
        
        # Request unload
        requests.post(LLM_API_URL, json={"model": model_name, "keep_alive": 0}, timeout=5)
        print(f"--- [VRAM: UNLOAD REQUESTED FOR {model_name}] ---")
        
        # Determine wait threshold based on model size
        # Qwen is ~14GB with graph, but we wait for 8GB release to be safe
        threshold = 8000 if "qwen" in model_name.lower() else 6000
        
        # Wait for the flush
        return vram_management.wait_for_vram_release(threshold) 
    except Exception as e:
        print(f"Failed to unload {model_name}: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) > 1:
        print(query_llm(" ".join(sys.argv[1:])))
