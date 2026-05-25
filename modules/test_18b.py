import urllib.request
import json
import time

url = "http://127.0.0.1:8082/v1/chat/completions"
prompt = """
You are a senior software engineer. Please build a multi-file TypeScript CLI tool called `config-check` that reads a JSON config file and validates it against a schema. 

Requirements:
1. Provide the code for `schema.ts`, `parser.ts`, and `cli.ts`.
2. Include the `tsconfig.json` configuration, specifically addressing `module` and `moduleResolution` (e.g., Node16) to avoid compilation errors.
3. Keep the code production-ready, typed, and clean.
"""

payload = {
    "model": "Qwopus-GLM-18B-Merged",
    "messages": [
        {"role": "user", "content": prompt}
    ],
    "temperature": 0.1,
    "max_tokens": 2000
}

req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'})

start_time = time.time()
try:
    print(f"[*] Sending 'config-check' CS test to local model at {url}...")
    with urllib.request.urlopen(req) as response:
        res = json.loads(response.read().decode())
        end_time = time.time()
        print(f"[*] Response received in {end_time - start_time:.2f} seconds.")
        print("-" * 60)
        
        message = res['choices'][0]['message']
        reasoning = message.get('reasoning_content', '')
        content = message.get('content', '')
        
        if reasoning:
            print(f"<think>\n{reasoning}\n</think>\n")
        print(content)
        
        print("-" * 60)
except Exception as e:
    print(f"[!] Error communicating with local model: {e}")
