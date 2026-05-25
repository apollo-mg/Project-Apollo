#!/bin/bash
# Setup Voxtral TTS for CPU Inference (AMD 5700X3D)

echo "🎙️ Initializing Voxtral TTS Setup..."

# 1. Create a dedicated directory
mkdir -p /mnt/TG_2TB/Projects/Apollo/voxtral
cd /mnt/TG_2TB/Projects/Apollo/voxtral

# 2. Clone the C-based inference engine
if [ ! -d "voxtral-tts.c" ]; then
    echo "[*] Cloning voxtral-tts.c repository..."
    git clone https://github.com/mudler/voxtral-tts.c.git
fi

cd voxtral-tts.c

# 3. Compile for CPU (AVX2 / 5700X3D optimizations)
echo "[*] Compiling Voxtral Engine for CPU..."
make -j$(nproc)

# 4. Download the Quantized Model (if not exists)
# Note: Since this is bleeding edge, we'll try to pull a Q4_K_M GGUF if available, 
# or default to the official huggingface repo if we need to use Python.
MODEL_DIR="/mnt/TG_2TB/Projects/Apollo/models"
MODEL_FILE="voxtral-4b-q4_k_m.gguf"

if [ ! -f "$MODEL_DIR/$MODEL_FILE" ]; then
    echo "[*] Model not found locally. We will need to pull the specific GGUF weights."
    echo "[*] For now, the C engine is compiled and ready."
else
    echo "[*] Found $MODEL_FILE in models directory."
fi

echo "✅ Setup script complete."
