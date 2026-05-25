import sys
import time
import requests
import numpy as np
import sounddevice as sd
import warnings
import io
import wave

warnings.filterwarnings("ignore")

WHISPER_SERVER_URL = "http://10.0.0.5:8080/inference" # We will need to update this to your desktop's IP
SAMPLE_RATE = 16000
CHUNK_SIZE = 1024
SILENCE_DURATION = 1.2
MAX_RECORD_TIME = 15.0

NOISE_HISTORY = []

def get_dynamic_threshold():
    global NOISE_HISTORY
    if not NOISE_HISTORY: return 0.04
    sorted_noise = sorted(NOISE_HISTORY)
    baseline = sorted_noise[int(len(sorted_noise) * 0.5)] 
    margin = 0.04
    return max(baseline + margin, 0.04)

def transcribe_audio(audio_data):
    wav_buffer = io.BytesIO()
    with wave.open(wav_buffer, 'wb') as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(SAMPLE_RATE)
        if audio_data.size == 0: return ""
        audio_int16 = (audio_data * 32767).astype(np.int16)
        f.writeframes(audio_int16.tobytes())
    
    wav_buffer.seek(0)
    files = {'file': ('audio.wav', wav_buffer, 'audio/wav')}
    data = {'response_format': 'json', 'temperature': '0.0'}
    
    try:
        response = requests.post(WHISPER_SERVER_URL, files=files, data=data, timeout=5)
        if response.status_code == 200:
            return response.json().get('text', '').strip()
    except Exception as e:
        print(f"\n[Satellite Error] {e}")
    return ""

def record_until_silence(stream, input_channels, native_sample_rate):
    print("\n[Satellite] Recording Command...")
    audio_data = []
    silent_chunks = 0
    has_started = False
    start_time = time.time()
    
    ratio = int(native_sample_rate / SAMPLE_RATE)
    local_chunk_size = CHUNK_SIZE * ratio
    
    while True:
        chunk, _ = stream.read(local_chunk_size)
        mono_chunk = chunk[:, 0] if input_channels > 1 else chunk.flatten()
        if ratio > 1: mono_chunk = mono_chunk[::ratio]
        
        audio_data.append(mono_chunk)
        vol = np.max(np.abs(mono_chunk))
        threshold = get_dynamic_threshold()
        
        if vol > threshold:
            has_started = True
            silent_chunks = 0
        else:
            if has_started:
                silent_chunks += 1
        
        if has_started and silent_chunks > (SILENCE_DURATION * (SAMPLE_RATE / CHUNK_SIZE)):
            break
        
        if not has_started and (time.time() - start_time) > 5.0:
            print("[Satellite] Command Timeout.")
            break
            
        if (time.time() - start_time) > MAX_RECORD_TIME:
            print("[Satellite] Max record time.")
            break
            
    return np.concatenate(audio_data).flatten()

def main():
    print("--- Zoey Voice Satellite Started ---")
    devices = sd.query_devices()
    
    input_device = None
    for i, dev in enumerate(devices):
        if "C922" in dev['name'] and dev['max_input_channels'] > 0:
            input_device = i
            break
            
    if input_device is None:
        input_device = 0
        
    device_info = devices[input_device]
    input_channels = int(device_info['max_input_channels'])
    native_sr = int(device_info['default_samplerate'])
    ratio = int(native_sr / SAMPLE_RATE)
    local_chunk_size = CHUNK_SIZE * ratio

    print(f"Using Mic: [{input_device}] {device_info['name']}")
    
    with sd.InputStream(device=input_device, samplerate=native_sr, channels=input_channels, dtype='float32') as stream:
        for _ in range(int(2.0 * SAMPLE_RATE / CHUNK_SIZE)):
            chunk, _ = stream.read(local_chunk_size)
            mono_chunk = chunk[:, 0] if input_channels > 1 else chunk.flatten()
            if ratio > 1: mono_chunk = mono_chunk[::ratio]
            vol = np.max(np.abs(mono_chunk))
            NOISE_HISTORY.append(vol)
    
    print(f"Noise Floor Set. Listening for wake word...")
    
    wake_buffer = []
    last_check_time = 0
    
    try:
        with sd.InputStream(device=input_device, samplerate=native_sr, channels=input_channels, dtype='float32') as stream:
            while True:
                chunk, _ = stream.read(local_chunk_size)
                mono_chunk = chunk[:, 0] if input_channels > 1 else chunk.flatten()
                if ratio > 1: mono_chunk = mono_chunk[::ratio]
                
                vol = np.max(np.abs(mono_chunk))
                NOISE_HISTORY.append(vol)
                if len(NOISE_HISTORY) > 500: NOISE_HISTORY.pop(0)
                
                wake_buffer.append(mono_chunk)
                max_buffer_chunks = int(3.0 * SAMPLE_RATE / CHUNK_SIZE)
                if len(wake_buffer) > max_buffer_chunks:
                    wake_buffer = wake_buffer[-max_buffer_chunks:]

                threshold = get_dynamic_threshold()
                current_time = time.time()
                
                if vol > threshold and (current_time - last_check_time) > 1.2:
                    if len(wake_buffer) > (1.5 * SAMPLE_RATE / CHUNK_SIZE):
                        extra_chunks = int(0.6 * SAMPLE_RATE / CHUNK_SIZE)
                        for _ in range(extra_chunks):
                            chunk, _ = stream.read(local_chunk_size)
                            mono_chunk = chunk[:, 0] if input_channels > 1 else chunk.flatten()
                            if ratio > 1: mono_chunk = mono_chunk[::ratio]
                            wake_buffer.append(mono_chunk)
                        
                        audio_check = np.concatenate(wake_buffer).flatten()
                        text = transcribe_audio(audio_check).lower().strip(".,? ")
                        last_check_time = time.time()
                        
                        if text:
                            print(f"Heard: {text}")
                            
                        phonetic_matches = ["zoe", "zoey", "zoie", "zowy", "zo e", "zo-e", "zoë", "zowie", "zoee", "so e", "soie", "soey"]
                        if any(variant in text for variant in phonetic_matches):
                            print(f"\n[WAKE WORD DETECTED] Triggered by: '{text}'")
                            
                            # WAKE SIGNAL: Tell desktop to play 'ready' sound
                            try:
                                requests.post("http://10.0.0.5:5000/wake", timeout=1)
                            except:
                                pass
                            
                            audio_cmd = record_until_silence(stream, input_channels, native_sr)
                            
                            print("[Satellite] Sending command to Whisper...")
                            user_cmd = transcribe_audio(audio_cmd)
                            
                            if user_cmd:
                                print(f"You: {user_cmd}")
                                # Send to Apollo Bridge on Desktop (Port 5000)
                                BRIDGE_URL = "http://10.0.0.5:5000/command"
                                try:
                                    requests.post(BRIDGE_URL, json={"text": user_cmd}, timeout=30)
                                    # SELF-DEAFENING: Avoid hearing the response from desktop speakers
                                    print("[Satellite] Self-Deafening for 15s...")
                                    time.sleep(15)
                                    # Clear buffer so we don't process the response as new audio
                                    wake_buffer = []
                                except Exception as e:
                                    print(f"[Satellite Bridge Error] {e}")
                                
                            wake_buffer = []

    except KeyboardInterrupt:
        print("\nStopping Satellite...")

if __name__ == '__main__':
    main()
