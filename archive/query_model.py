import sys
import json
import urllib.request

def query_model(system_file, user_message):
    with open(system_file, 'r') as f:
        system_prompt = f.read()

    data = {
        "model": "zoey-35b-moe", # arbitrary model name, maybe it accepts anything or requires specific, we can just use default if vllm
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        "temperature": 0.7,
        "max_tokens": 150
    }
    
    req = urllib.request.Request(
        'http://10.0.0.5:11435/v1/chat/completions',
        data=json.dumps(data).encode('utf-8'),
        headers={'Content-Type': 'application/json'}
    )
    
    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode('utf-8'))
            print(result['choices'][0]['message']['content'])
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python3 query_model.py <system_prompt_file> <user_message>")
        sys.exit(1)
    query_model(sys.argv[1], sys.argv[2])
