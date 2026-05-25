import base64
import requests
import json
import os

# Configuration
IMAGE_PATH = os.path.expanduser("~/Project-Apollo/test_known.jpg")
API_URL = "http://10.0.0.5:11435/v1/chat/completions"

def test_native_vision():
    if not os.path.exists(IMAGE_PATH):
        print(f"Error: Image not found at {IMAGE_PATH}")
        return

    print(f"[*] Encoding image: {IMAGE_PATH}...")
    with open(IMAGE_PATH, "rb") as image_file:
        base64_image = base64.b64encode(image_file.read()).decode('utf-8')

    print("[*] Sending native vision request to Workstation (10.0.0.5)...")
    
    payload = {
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Analyze this image natively. What do you see on Mark's workbench? Provide a technical summary."},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}"
                        }
                    }
                ]
            }
        ],
        "max_tokens": 1000
    }

    try:
        response = requests.post(API_URL, json=payload, timeout=120)
        if response.status_code == 200:
            result = response.json()
            print("\n[Architect Response]:")
            print(result['choices'][0]['message']['content'])
        else:
            print(f"Error: Server returned {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_native_vision()
