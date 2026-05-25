#!/bin/bash

# ==============================================================================
# Sovereign Engine: Bonsai-8B (1-bit KAIROS Subconscious Daemon)
# ==============================================================================
# This script launches the 1-bit quantized Bonsai-8B model on port 8083.
# It MUST use the `prism_llama_cpp` fork, as the standard `llama.cpp` does not 
# currently support the BitNet/IQ1_S ggml type 41 tensors on ROCm.
# ==============================================================================

PORT=8083
MODEL_PATH="/mnt/TG_2TB/Projects/Apollo/models/Bonsai-8B.gguf"
SERVER_BIN="/mnt/TG_2TB/Projects/Apollo/engines/prism_llama_cpp/build/bin/llama-server"
LOG_FILE="/mnt/TG_2TB/Projects/Apollo/bonsai_server.log"

echo "🌱 Starting Bonsai-8B 1-bit KAIROS Daemon..."
echo "🔌 Port: $PORT"
echo "🧠 Model: $MODEL_PATH"
echo "⚙️  Backend: ROCm (PrismML Fork)"
echo "📝 Log: $LOG_FILE"
echo "--------------------------------------------------------------------------------"

# Kill any existing server on this port to prevent bind errors
fuser -k $PORT/tcp 2>/dev/null

# Launch the server in the background
nohup $SERVER_BIN \
  -m $MODEL_PATH \
  -c 4096 \
  -np 1 \
  --port $PORT \
  --host 127.0.0.1 \
  -ngl 99 \
  --alias "Bonsai-8B" \
  > $LOG_FILE 2>&1 &

echo "✅ Bonsai-8B is booting in the background."
echo "Use 'tail -f bonsai_server.log' to monitor the startup process."