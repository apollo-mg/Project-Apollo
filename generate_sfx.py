import numpy as np
import scipy.io.wavfile as wav
import os

SOUND_DIR = r"C:\gemini_infrastructure\sounds"
if not os.path.exists(SOUND_DIR):
    os.makedirs(SOUND_DIR)

def save_wav(filename, data, rate=44100):
    # Normalize to 16-bit PCM
    scaled = np.int16(data / np.max(np.abs(data)) * 32767)
    wav.write(os.path.join(SOUND_DIR, filename), rate, scaled)

def generate_chirp(start_freq, end_freq, duration, rate=44100):
    t = np.linspace(0, duration, int(rate * duration), endpoint=False)
    # Linear chirp
    frequencies = np.linspace(start_freq, end_freq, len(t))
    phase = 2 * np.pi * np.cumsum(frequencies) / rate
    envelope = np.exp(-5 * t)  # Decay
    return np.sin(phase) * envelope

def generate_ready_sound():
    # A quick, high-tech "blip-blip"
    rate = 44100
    duration = 0.15
    t = np.linspace(0, duration, int(rate * duration), endpoint=False)
    
    tone1 = np.sin(2 * np.pi * 1200 * t) * np.exp(-10 * t)
    tone2 = np.sin(2 * np.pi * 1800 * t) * np.exp(-10 * t)
    
    # Silence between blips
    silence = np.zeros(int(rate * 0.05))
    
    audio = np.concatenate([tone1, silence, tone2])
    save_wav("ready.wav", audio)

def generate_relay_sound():
    # A "computing" data transfer sound
    rate = 44100
    t = np.linspace(0, 0.4, int(rate * 0.4), endpoint=False)
    # FM Synthesis for sci-fi texture
    carrier = 880
    modulator = 220
    index = 5
    
    audio = np.sin(2 * np.pi * carrier * t + index * np.sin(2 * np.pi * modulator * t))
    audio *= np.linspace(1, 0, len(audio)) # Fade out
    save_wav("relay.wav", audio)

def generate_processing_sound():
    # A low, rhythmic "thinking" hum
    rate = 44100
    t = np.linspace(0, 0.5, int(rate * 0.5), endpoint=False)
    audio = np.sin(2 * np.pi * 200 * t) * 0.5 + np.sin(2 * np.pi * 205 * t) * 0.5
    # Add some high freq sparkles
    sparkle = np.sin(2 * np.pi * 2000 * t) * (np.sin(2 * np.pi * 20 * t) > 0.8) * 0.1
    save_wav("processing.wav", audio + sparkle)

if __name__ == "__main__":
    print("Generating sounds...")
    generate_ready_sound()
    generate_relay_sound()
    generate_processing_sound()
    print(f"Sounds saved to {SOUND_DIR}")
