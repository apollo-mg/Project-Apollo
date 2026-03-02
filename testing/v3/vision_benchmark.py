import urllib.request
import json
import time
import base64
import os

OLLAMA_API = "http://localhost:11434/api/generate"
MODEL_V3 = "qwen3-vl:8b"
MODEL_V2 = "qwen2.5vl:latest"

# Path to a test image - we'll use the one we saw earlier in the directory
TEST_IMAGE = "/home/mark/gemini/20260227_001025.jpg"

def encode_image(image_path):
    if not os.path.exists(image_path):
        return None
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")

def query_vision(model, prompt_text, image_b64):
    data = json.dumps({
        "model": model,
        "prompt": prompt_text,
        "images": [image_b64],
        "stream": False,
        "options": {"temperature": 0.2}
    }).encode("utf-8")
    
    req = urllib.request.Request(OLLAMA_API, data=data, headers={"Content-Type": "application/json"})
    
    start_time = time.time()
    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode("utf-8"))
            eval_duration_s = result.get("eval_duration", 0) / 1e9
            eval_count = result.get("eval_count", 0)
            tps = eval_count / eval_duration_s if eval_duration_s > 0 else 0
            return {
                "response": result.get("response", ""),
                "tps": tps,
                "total_time": time.time() - start_time
            }
    except Exception as e:
        return {"error": str(e)}

def run_benchmark():
    img_b64 = encode_image(TEST_IMAGE)
    if not img_b64:
        print(f"Error: Test image not found at {TEST_IMAGE}")
        return

    prompt = "Describe this image in detail. Identify any hardware, tools, or electronics you see."
    
    for model in [MODEL_V2, MODEL_V3]:
        print(f"\n--- Benchmarking {model} ---")
        res = query_vision(model, prompt, img_b64)
        if "error" in res:
            print(f"Error: {res['error']}")
            continue
        
        print(f"Response (truncated):\n{res['response'][:500]}...")
        print(f"\nMetrics: {res['tps']:.2f} tokens/sec | Total Time: {res['total_time']:.2f}s")

if __name__ == "__main__":
    run_benchmark()
