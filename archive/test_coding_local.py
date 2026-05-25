import requests
import time
import sys

prompt = "Write a Python script that takes a list of integers and returns the length of the longest strictly increasing contiguous subsegment. Keep the explanation very brief, just provide the code."

payload = {
    "messages": [
        {"role": "user", "content": prompt}
    ],
    "temperature": 0.1,
    "max_tokens": 500
}

url = "http://10.0.0.5:11435/v1/chat/completions"
print(f"Sending prompt to Local Sovereign Engine ({url})...")
print(f"Prompt: {prompt}\n")

start_time = time.time()
try:
    res = requests.post(url, json=payload, timeout=60)
    res.raise_for_status()
    data = res.json()
    end_time = time.time()
    
    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    print("=== LOCAL MODEL OUTPUT ===")
    print(content)
    print("==========================")
    print(f"\nLocal Generation Time: {end_time - start_time:.2f} seconds")
except Exception as e:
    print(f"Failed to reach local model: {e}")
