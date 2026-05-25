#!/bin/bash
# Setup Voxtral TTS Q4 (Rust/Burn Engine)

echo "🎙️ Initializing Quantized Voxtral TTS Setup..."

source $HOME/.cargo/env

mkdir -p /mnt/TG_2TB/Projects/Apollo/voxtral_rust
cd /mnt/TG_2TB/Projects/Apollo/voxtral_rust

if [ ! -d "voxtral-mini-realtime-rs" ]; then
    echo "[*] Cloning voxtral-mini-realtime-rs repository..."
    git clone https://github.com/TrevorS/voxtral-mini-realtime-rs.git
fi

cd voxtral-mini-realtime-rs

echo "[*] Compiling Rust Engine..."
# Build without WGPU first to ensure pure CPU inference on the 5700X3D if they want.
# Actually, the repo suggests WGPU for fast inference. We will build with WGPU.
cargo build --release --features "wgpu,cli,hub" --bin voxtral

echo "[*] Downloading Q4 GGUF Model..."
MODEL_DIR="/mnt/TG_2TB/Projects/Apollo/models"
wget -nc -O $MODEL_DIR/voxtral-tts-q4.gguf https://huggingface.co/TrevorJS/voxtral-tts-q4-gguf/resolve/main/voxtral-tts-q4.gguf

echo "✅ Q4 Setup script complete."
