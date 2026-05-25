import os
import sys
from google import genai
from dotenv import load_dotenv

load_dotenv("/media/mark/48B42D2CB42D1DC6/gemini_infrastructure/.env.jarvis")
API_KEY = os.getenv("GOOGLE_API_KEY")

def list_models():
    if not API_KEY:
        print("Error: GOOGLE_API_KEY not found.")
        return

    try:
        client = genai.Client(api_key=API_KEY, http_options={'api_version': 'v1beta'})
        print("Model list (v1beta):")
        for m in client.models.list():
            # Check if it's gemini 2.0
            if "gemini-2.0" in m.name:
                print(f"--- {m.name} ---")
                # Print all attributes to see which ones are available
                # print(dir(m))
                try:
                    # 'methods' is often used in newer SDKs
                    print(f"  Metadata: {m}")
                except:
                    pass
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    list_models()
