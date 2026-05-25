#!/bin/bash
echo "[*] Setting up Sovereign Audio Stack..."

# 1. Install system dependencies (PortAudio is required for PyAudio)
echo "[*] Checking system packages (requires sudo for portaudio)..."
sudo pacman -S --needed --noconfirm portaudio base-devel

# 2. Activate virtual environment and install Python packages
echo "[*] Activating venv_cachyos..."
source /mnt/TG_2TB/Projects/Apollo/venv_cachyos/bin/activate

echo "[*] Installing Python audio dependencies..."
pip install pyaudio webrtcvad sounddevice openwakeword

echo "[*] Audio stack installed successfully. Ready for wake_up.py."
