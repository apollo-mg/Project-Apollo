#!/bin/bash
echo "Starting ROCm-Accelerated Whisper Server..."
# Using the large v3 turbo quant for speed + accuracy
MODEL_PATH="/home/mark/gemini/whisper.cpp/models/ggml-large-v3-turbo-q5_0.bin"
BINARY="/home/mark/gemini/whisper.cpp/build/bin/whisper-server"

if [ ! -f "$BINARY" ]; then
    echo "Error: whisper-server binary not found."
    exit 1
fi

if [ ! -f "$MODEL_PATH" ]; then
    echo "Error: Model file not found at $MODEL_PATH"
    exit 1
fi

# -fa enables flash attention (faster)
# -dev 0 targets the primary GPU
# -ng removes it, we want GPU so we don't use -ng
$BINARY -m "$MODEL_PATH" --host 0.0.0.0 --port 8080 -fa
