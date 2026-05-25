#!/bin/bash
set -e

echo "=========================================================="
echo "   PROJECT APOLLO: SWARM ORCHESTRATION BOOTSTRAP          "
echo "=========================================================="
echo " This script initializes the Apollo Orchestration Layer.  "
echo " It assumes you are bringing your own OpenAI-compatible   "
echo " inference engine (llama.cpp, vLLM, Ollama, etc.).        "
echo "=========================================================="

WORKSPACE=$(pwd)
VENV_DIR="$WORKSPACE/.venv"

echo -e "\n[1/4] Checking Prerequisites..."
command -v python3 >/dev/null 2>&1 || { echo "❌ python3 is required but not installed. Aborting." >&2; exit 1; }
command -v npm >/dev/null 2>&1 || { echo "❌ npm/node is required but not installed. Aborting." >&2; exit 1; }

echo -e "\n[2/4] Setting up Python Environment for Workers/Daemons..."
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
    echo "✅ Virtual environment created at $VENV_DIR"
else
    echo "⚡ Virtual environment already exists."
fi

source "$VENV_DIR/bin/activate"
pip install --upgrade pip > /dev/null

echo "📦 Installing core Python orchestration dependencies..."
# We only install the lightweight HTTP/routing packages, NOT PyTorch!
pip install fastapi uvicorn mcp aiohttp pydantic pyyaml > /dev/null
echo "✅ Python dependencies installed."

echo -e "\n[3/4] Setting up Node.js Environment for Apollo Server..."
cd "$WORKSPACE/engines/open-multi-agent-upstream"
echo "📦 Installing Node dependencies..."
npm install > /dev/null
echo "✅ Node dependencies installed."

echo -e "\n[4/4] Generating .env template..."
cd "$WORKSPACE"
if [ ! -f ".env" ]; then
    cat << 'ENVEOF' > .env
# Project Apollo Configuration
APOLLO_ROOT=/path/to/Project-Apollo

# Bring Your Own Engine (BYOE)
# Point this to your existing llama-server, vLLM, or Ollama instance
LLM_ENDPOINT=http://127.0.0.1:8082/v1
OPENAI_API_KEY=sk-local-apollo

# Message Bus Connection
MESSAGE_BUS_API=http://127.0.0.1:8000
ENVEOF
    echo "✅ Created .env template."
    echo "⚠️  ACTION REQUIRED: Edit .env and set APOLLO_ROOT to your absolute path."
else
    echo "⚡ .env already exists."
fi

echo -e "\n=========================================================="
echo "   BOOTSTRAP COMPLETE!                                    "
echo "=========================================================="
echo " To start the Swarm:"
echo " 1. Ensure your inference engine is running at the LLM_ENDPOINT in .env"
echo " 2. Start the Message Bus: cd deploy && docker compose up -d"
echo " 3. Start the Apollo Architect: cd engines/open-multi-agent-upstream && npm run start"
echo "=========================================================="