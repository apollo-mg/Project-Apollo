import subprocess
import os
import time
import platform
import requests
import base64

ARCHITECT_API = "http://127.0.0.1:8082/v1/chat/completions"
MODEL_NAME = "Qwen3.5-35B-A3B-Uncensored-HauhauCS-Aggressive-IQ2_M.gguf"

def capture_screen(filename="latest_screenshot.png"):
    """
    Captures the primary monitor and saves it to the specified filename.
    Returns the absolute path to the screenshot.
    """
    output_path = os.path.abspath(filename)
    try:
        if platform.system() == "Windows":
            from PIL import ImageGrab
            screenshot = ImageGrab.grab()
            screenshot.save(output_path)
            return output_path
        else:
            # Use spectacle for capture (KDE native, works on X11 and Wayland)
            # Must set DISPLAY explicitly if run from headless shell
            env = os.environ.copy()
            if "DISPLAY" not in env:
                env["DISPLAY"] = ":0"
            subprocess.run(["spectacle", "-b", "-n", "-o", output_path], check=True, env=env)
            return output_path
    except Exception as e:
        print(f"Error capturing screen: {e}")
        return None

def analyze_desktop(prompt="What do you see on my screen? Be brief."):
    """
    Takes a screenshot and sends it directly to the local 35B MoE Architect.
    """
    print("[*] Capturing desktop...")
    img_path = capture_screen()
    
    if not img_path:
        return "Failed to capture screen."

    print("[*] Sending visual data to 35B Architect...")
    try:
        from PIL import Image
        import io
        with Image.open(img_path) as img:
            if img.mode != 'RGB':
                img = img.convert('RGB')
            img.thumbnail((1280, 1280))
            buffered = io.BytesIO()
            img.save(buffered, format="JPEG", quality=85)
            img_data = base64.b64encode(buffered.getvalue()).decode('utf-8')
    except Exception as e:
        print(f"[-] Image downscale failed, using raw: {e}")
        with open(img_path, "rb") as f:
            img_data = base64.b64encode(f.read()).decode('utf-8')

    payload = {
        'model': MODEL_NAME,
        'messages': [
            {
                'role': 'user',
                'content': [
                    {'type': 'text', 'text': prompt},
                    {'type': 'image_url', 'image_url': {'url': f'data:image/png;base64,{img_data}'}}
                ]
            }
        ],
        'stream': False,
        'max_tokens': 1024,
        'temperature': 0.6,
        'repeat_penalty': 1.1
    }

    try:
        res = requests.post(ARCHITECT_API, json=payload, timeout=600)
        res.raise_for_status()
        msg = res.json()['choices'][0]['message']
        reasoning = msg.get('reasoning_content', '') or ""
        content = msg.get('content', '') or ""
        return (reasoning + "\n" + content).strip()
    except Exception as e:
        return f"[-] Error contacting Architect: {e}"

if __name__ == "__main__":
    print(analyze_desktop())