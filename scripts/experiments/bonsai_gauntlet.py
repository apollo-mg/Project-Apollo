import requests
import time

URL = "http://127.0.0.1:8083/v1/chat/completions"

TASKS = {
    "1. Logic & Reasoning": "If I have a 5-liter jug and a 3-liter jug, and an unlimited supply of water, how can I measure exactly 4 liters? Be concise.",
    "2. Coding (Python)": "Write a Python function to compute the Fibonacci sequence up to n using a generator.",
    "3. Summarization": "Summarize the core architectural difference between a standard Transformer and a Mixture of Experts (MoE) model in two sentences.",
    "4. Fact Retrieval": "Who was the primary architect of the Apollo 11 Lunar Module? Respond with just the name.",
    "5. JSON Formatting": "Output a valid JSON object containing three keys: 'name' (string), 'age' (integer), and 'skills' (list of strings). Do not include any markdown formatting, just the raw JSON."
}

print("========================================")
print("   BONSAI-8B (1-BIT) CAPABILITY GAUNTLET")
print("========================================\n")

for task_name, prompt in TASKS.items():
    print(f"\n--- {task_name} ---")
    payload = {
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.1,
        "max_tokens": 512
    }
    
    start = time.time()
    try:
        res = requests.post(URL, json=payload, timeout=120)
        res.raise_for_status()
        data = res.json()
        content = data['choices'][0]['message']['content'].strip()
        tokens = data['usage']['completion_tokens']
        tps = tokens / (time.time() - start)
        
        print(f"Response:\n{content}\n")
        print(f"[Stats: {tokens} tokens | {tps:.1f} TPS]")
    except Exception as e:
        print(f"❌ Failed: {e}")
    print("----------------------------------------")
