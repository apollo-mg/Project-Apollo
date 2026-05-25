import requests
import time

API_URL = "http://127.0.0.1:8082/v1/chat/completions"

def run_benchmark():
    prompt = "Solve this logic puzzle: Three friends check into a hotel. They pay $30 to the manager and go to their room. The manager finds out that the room rate is $25 and gives $5 to the bellboy to return. On the way, the bellboy reasons that $5 would be difficult to share among three people so he pockets $2 and gives $1 to each person. Now, each person paid $10 and got back $1. So they paid $9 each, totalling $27. The bellboy has $2, totalling $29. Where is the remaining $1? Explain step by step."

    payload = {
        "messages": [
            {"role": "system", "content": "You are a logical reasoning AI."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.1,
        "max_tokens": 512,
        "stream": False
    }

    print("[*] Sending request to llama-server...")
    start_time = time.time()
    
    try:
        response = requests.post(API_URL, json=payload, timeout=120)
        response.raise_for_status()
        
        end_time = time.time()
        elapsed = end_time - start_time
        
        data = response.json()
        content = data['choices'][0]['message']['content']
        usage = data.get('usage', {})
        
        completion_tokens = usage.get('completion_tokens', 0)
        prompt_tokens = usage.get('prompt_tokens', 0)
        
        tps = completion_tokens / elapsed if elapsed > 0 else 0
        
        print(f"\n--- Benchmark Results ---")
        print(f"Time Elapsed: {elapsed:.2f}s")
        print(f"Prompt Tokens: {prompt_tokens}")
        print(f"Generation Tokens: {completion_tokens}")
        print(f"Generation Speed: {tps:.2f} tokens/sec")
        print(f"\n--- Output Sample ---")
        print(content[:300] + "...\n")
        
    except Exception as e:
        print(f"[!] Benchmark failed: {e}")

if __name__ == "__main__":
    run_benchmark()
