import urllib.request
import json
import time

OLLAMA_API = "http://localhost:11434/api/generate"

# Using Qwen2.5 0.5B as the stand-in for Qwen3 0.6B
MODELS = ["functiongemma:270m", "qwen2.5:0.5b", "llama3.2:1b"]

SYSTEM_PROMPT = """You are the Apollo Dispatcher. Your job is to route user requests.
CRITICAL: Return ONLY a raw JSON object. NO markdown. NO preamble. NO conversational text.

MODULES: DEV, SHOP, DEEP_THINK, ARCHITECT, SYSTEM, CHITCHAT

EXAMPLES:
User: "Write a script." -> {"module": "DEV", "priority": "P2"}
User: "Scan this PCB." -> {"module": "SHOP", "priority": "P1"}
User: "Debug this race condition." -> {"module": "DEEP_THINK", "priority": "P1"}
"""

TEST_CASES = [
    "Write a python script to parse a csv file.",
    "How much VRAM am I using?",
    "I need a complete architectural refactor of the Vault."
]

def query_model(model_name, prompt):
    data = json.dumps({
        "model": model_name,
        "prompt": f"{SYSTEM_PROMPT}\nUser: {prompt}\nJSON:\n",
        "stream": False,
        "options": {"temperature": 0.1, "num_predict": 50}
    }).encode("utf-8")
    
    req = urllib.request.Request(OLLAMA_API, data=data, headers={"Content-Type": "application/json"})
    
    start = time.time()
    try:
        with urllib.request.urlopen(req) as response:
            res = json.loads(response.read().decode("utf-8"))
            eval_duration_s = res.get("eval_duration", 0) / 1e9
            eval_count = res.get("eval_count", 0)
            tps = eval_count / eval_duration_s if eval_duration_s > 0 else 0
            return res.get("response", ""), tps, time.time() - start
    except Exception as e:
        return f"Error: {e}", 0, 0

def run_shootout():
    print("--- 🔫 SUB-BILLION RECEPTIONIST SHOOTOUT ---")
    for prompt in TEST_CASES:
        print(f"\n[Test Case]: {prompt}")
        print("-" * 50)
        for model in MODELS:
            response, tps, total_time = query_model(model, prompt)
            clean_resp = response.strip().replace('\n', ' ')
            print(f"[{model.ljust(20)}] | TPS: {tps:6.2f} | Time: {total_time:4.2f}s | Output: {clean_resp[:80]}")

if __name__ == "__main__":
    run_shootout()
