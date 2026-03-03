import requests
import json
from llm_interface import encode_image

img1 = encode_image("tmp/vision/20260302_192022.jpg")
img2 = encode_image("tmp/vision/20260302_192033.jpg")

payload = {
    "model": "qwen3-vl:8b",
    "stream": False,
    "messages": [
        {
            "role": "user",
            "content": "Identify the text on this board.",
            "images": [img1, img2]
        }
    ],
    "options": {"num_ctx": 8192}
}

r = requests.post("http://127.0.0.1:11434/api/chat", json=payload)
print(r.json())
