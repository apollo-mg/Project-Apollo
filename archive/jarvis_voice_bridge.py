import asyncio
import base64
import json
import os
import sys
import sounddevice as sd
import numpy as np
from google import genai
from dotenv import load_dotenv

# CONFIGURATION
load_dotenv("/media/mark/48B42D2CB42D1DC6/gemini_infrastructure/.env.jarvis")
API_KEY = os.getenv("GOOGLE_API_KEY")

# Use the specific ID that supports bidiGenerateContent
MODEL_ID = "gemini-2.0-flash-exp-image-generation" 

# AUDIO PARAMETERS
SAMPLE_RATE = 16000
CHANNELS = 1
CHUNK_SIZE = 512

async def main():
    if not API_KEY:
        print("Error: GOOGLE_API_KEY not found in .env.jarvis")
        sys.exit(1)

    # Use v1beta - this is the current required version for Multimodal Live
    client = genai.Client(api_key=API_KEY, http_options={'api_version': 'v1beta'})
    
    # List devices to help debugging
    devices = sd.query_devices()
    input_device = None
    print("Detecting Audio Devices...")
    
    # Priority 1: Search for 'Jarvis' or 'Virtual'
    for i, dev in enumerate(devices):
        if "Jarvis" in dev['name'] or "Virtual" in dev['name']:
            input_device = i
            break
            
    # Priority 2: Fallback to PipeWire/Pulse wrappers if available
    if input_device is None:
        for i, dev in enumerate(devices):
            if dev['name'] in ["pipewire", "pulse", "default"]:
                input_device = i
                break

    if input_device is None:
        input_device = sd.default.device[0]

    print(f"---> Selected Input: [{input_device}] {devices[input_device]['name']}")

    # Audio Playback stream (Output)
    output_stream = sd.OutputStream(samplerate=24000, channels=1, dtype='int16')
    output_stream.start()

    loop = asyncio.get_event_loop()

    def audio_callback(indata, frames, time, status):
        if status:
            print(status, file=sys.stderr)
        try:
            asyncio.run_coroutine_threadsafe(
                session.send({"data": base64.b64encode(indata).decode('utf-8'), "mime_type": "audio/pcm"}),
                loop
            )
        except Exception:
            pass

    input_stream = sd.InputStream(device=input_device, channels=CHANNELS, samplerate=SAMPLE_RATE, 
                                  dtype='int16', callback=audio_callback, blocksize=CHUNK_SIZE)

    try:
        # Multimodal Live API call using v1beta
        async with client.aio.live.connect(model=MODEL_ID, config={"response_modalities": ["AUDIO"]}) as session:
            print("\nConnected to Gemini Live. Start speaking!")
            input_stream.start()

            async for message in session:
                if "server_content" in message:
                    content = message["server_content"]
                    if "model_turn" in content:
                        parts = content["model_turn"]["parts"]
                        for part in parts:
                            if "inline_data" in part:
                                audio_data = base64.b64decode(part["inline_data"]["data"])
                                audio_array = np.frombuffer(audio_data, dtype='int16')
                                output_stream.write(audio_array)

                if "tool_call" in message:
                    print("\n[Jarvis] Tool Call requested by AI.")

    except KeyboardInterrupt:
        print("\nStopping Jarvis Voice Bridge...")
    except Exception as e:
        print(f"\nConnection Error: {e}")
        print("\nTIP: Go to https://aistudio.google.com/ and create a NEW API Key.")
        print("Make sure you are NOT using a Google Cloud Service Account key.")
    finally:
        input_stream.stop()
        input_stream.close()
        output_stream.stop()
        output_stream.close()

if __name__ == "__main__":
    asyncio.run(main())
