import os
import subprocess
import tempfile
import threading

PIPER_BIN = "/mnt/TG_2TB/Projects/Apollo/venv_cachyos/bin/piper"
MODEL_ONNX = "/mnt/TG_2TB/Projects/Apollo/models/piper/en_US-lessac-medium.onnx"

def _speak_thread(text):
    """Internal thread to run Piper inference and play audio."""
    print(f"🎙️ [Piper TTS] Synthesizing: '{text[:40]}...'")
    
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_wav:
        out_path = tmp_wav.name
        
    piper_cmd = [
        PIPER_BIN,
        "--model", MODEL_ONNX,
        "--output_file", out_path
    ]
    
    try:
        # Start the piper process
        piper_proc = subprocess.Popen(
            piper_cmd, 
            stdin=subprocess.PIPE, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE # Capture stderr so we see errors
        )
        
        # Feed the text to piper
        _, stderr_data = piper_proc.communicate(input=text.encode('utf-8'))
        
        if piper_proc.returncode != 0:
            print(f"❌ [Piper Error]: {stderr_data.decode('utf-8')}")
            return
            
        # Play the audio using pw-play (PipeWire native player)
        # This guarantees it uses the KDE Plasma default sink (like your Line Out)
        subprocess.run(["pw-play", out_path])
        
    except Exception as e:
        print(f"❌ [Voice System Error]: {e}")
    finally:
        if os.path.exists(out_path):
            os.remove(out_path)

def speak(text, block=False):
    """
    Speaks the given text using Piper TTS.
    If block is True, it waits for the audio to finish. Otherwise, it runs in the background.
    """
    # Clean the text of markdown/emojis
    clean_text = text.replace("*", "").replace("`", "").replace("_", "")
    
    if block:
        _speak_thread(clean_text)
    else:
        t = threading.Thread(target=_speak_thread, args=(clean_text,))
        t.start()

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        speak(" ".join(sys.argv[1:]), block=True)
    else:
        speak("Tactical audio interface online. Awaiting coordinates.", block=True)
