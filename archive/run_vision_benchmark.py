import requests
import json
import time
import subprocess
import os
import sys
import base64

if len(sys.argv) < 3:
    print("Usage: python run_vision_benchmark.py <path_to_model> <path_to_mmproj>")
    sys.exit(1)

MODEL_PATH = sys.argv[1]
MMPROJ_PATH = sys.argv[2]
API_URL = "http://127.0.0.1:8082/v1/chat/completions"

def spin_up_server():
    print(f"[*] Starting llama-server with vision module...")
    os.system("pkill -9 llama-server")
    time.sleep(1)
    
    cmd = [
        "llama.cpp/build/bin/llama-server",
        "-m", MODEL_PATH,
        "--mmproj", MMPROJ_PATH,
        "--port", "8082",
        "-ngl", "99",
        "-c", "8192"
    ]
    process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    for i in range(25):
        try:
            r = requests.get("http://127.0.0.1:8082/health")
            if r.status_code == 200:
                print(f"[*] Server Online! (PID: {process.pid})")
                return process
        except:
            pass
        time.sleep(2)
    return process

def run_vision_test():
    img_path = "/home/mark/Downloads/20260322_180010.jpg"
    try:
        with open(img_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
    except Exception as e:
        print(f"Error loading image: {e}")
        return

    # Using standard base64 embedding format, some newer servers prefer just the raw b64
    payload = {
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{encoded_string}"
                        }
                    },
                    {"type": "text", "text": "Describe exactly what you see in this image. Do not hallucinate."}
                ]
            }
        ],
        "temperature": 0.2,
        "max_tokens": 512,
        "stream": False
    }

    print("[*] Sending image payload to server...")
    start_time = time.time()
    try:
        response = requests.post(API_URL, json=payload, timeout=300)
        
        if response.status_code != 200:
            print(f"[!] Server returned {response.status_code}")
            print(response.text)
            return

        data = response.json()
        content = data['choices'][0]['message']['content']
        print(f"\n[Vision Test Result]:\n{content}\n")
    except Exception as e:
        print(f"[!] Vision API Error: {e}")

if __name__ == "__main__":
    process = spin_up_server()
    if process:
        run_vision_test()
        process.terminate()
        process.wait()
