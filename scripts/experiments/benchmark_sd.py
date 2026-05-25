import time
import requests

url = "http://localhost:8082/v1/chat/completions"
headers = {"Content-Type": "application/json"}

# This prompt forces highly repetitive JSON boilerplate
data = {
    "model": "qwen3.6",
    "messages": [
        {"role": "system", "content": "You are a data generator. Output raw JSON only."},
        {"role": "user", "content": "Generate a JSON array containing 50 user objects. Each object must have exactly these fields: id (UUID), name(string), email (string), isActive (boolean), createdAt (ISO 8601 timestamp), and preferences (object with theme: dark/light, notifications: true/false)."}
    ],
    "max_tokens": 4000,
    "temperature": 0.0, # Zero temp ensures deterministic tokens for the n-gram cache
    "stream": False
}

print("Starting benchmark...")
start_time = time.time()

response = requests.post(url, headers=headers, json=data).json()

end_time = time.time()
total_time = end_time - start_time

usage = response.get("usage", {})
output_tokens = usage.get("completion_tokens", 0)

# llama.cpp usually includes specific timing info in the raw response
print(f"\n--- Results ---")
print(f"Total Time: {total_time:.2f} seconds")
print(f"Tokens Generated: {output_tokens}")
if output_tokens > 0:
    print(f"Speed: {(output_tokens / total_time):.2f} tokens/second")
