import urllib.request
import json
import time

OLLAMA_API = "http://localhost:11434/api/generate"
MODEL = "qwen3:8b"

PROMPTS = [
    {
        "name": "Trick Logic",
        "prompt": "A farmer has 10 sheep. All but 9 die. How many are left? Think step-by-step."
    },
    {
        "name": "Coding (Levenshtein)",
        "prompt": "Write a concise Python function to compute the Levenshtein distance between two strings without using any external libraries."
    },
    {
        "name": "Reasoning (GIL & Concurrency)",
        "prompt": "Explain the difference between threading and multiprocessing in Python. Specifically address how the Global Interpreter Lock (GIL) affects CPU-bound vs I/O-bound tasks."
    },
    {
        "name": "Spatial/Logic (Water Jugs)",
        "prompt": "I have an unlimited water supply, a 3-gallon jug, and a 5-gallon jug. How can I measure exactly 4 gallons of water? Provide the exact sequence of steps."
    }
]

def query_ollama(prompt_text):
    data = json.dumps({
        "model": MODEL,
        "prompt": prompt_text,
        "stream": False,
        "options": {
            "temperature": 0.3
        }
    }).encode("utf-8")
    
    req = urllib.request.Request(OLLAMA_API, data=data, headers={"Content-Type": "application/json"})
    
    start_time = time.time()
    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode("utf-8"))
            
            # eval_duration is in nanoseconds
            eval_duration_s = result.get("eval_duration", 0) / 1e9
            eval_count = result.get("eval_count", 0)
            
            tps = eval_count / eval_duration_s if eval_duration_s > 0 else 0
            
            return {
                "response": result.get("response", ""),
                "tps": tps,
                "total_time": time.time() - start_time,
                "eval_count": eval_count
            }
    except Exception as e:
        return {"error": str(e)}

def run_tests():
    print(f"--- Benchmarking {MODEL} ---")
    for p in PROMPTS:
        print("")
        print(f"[Test: {p['name']}]")
        print(f"Prompt: {p['prompt']}")
        print("Running...")
        
        res = query_ollama(p["prompt"])
        if "error" in res:
            print(f"Error: {res['error']}")
            continue
            
        print("")
        print("Response:")
        print("-" * 40)
        print(res["response"].strip())
        print("-" * 40)
        print(f"Metrics: {res['eval_count']} tokens | {res['tps']:.2f} tokens/sec | Total Time: {res['total_time']:.2f}s")

if __name__ == "__main__":
    run_tests()
