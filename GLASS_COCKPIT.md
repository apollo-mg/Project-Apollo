# 🎛️ APOLLO GLASS COCKPIT
**The Central Command & Master Registry for Project Apollo**

*This document serves as the "Visual Basic Project Explorer" for Mark. Every background script, daemon, and bridge created by an AI agent MUST be registered here in plain English.*

---

## 🧠 1. The Memory Pipeline (The "Neurosama" Architecture)

This system gives the 35B MoE the illusion of infinite memory without crashing your VRAM. It consists of two parts: the Archivist (which extracts facts) and the Bridge (which injects them).

### A. The Archivist (`liara_indexer.py`)
* **What it does:** Runs quietly in the background. It reads your chat logs, uses a small CPU-based model to extract core engineering facts (hardware specs, project decisions), and saves them to `data/apollo_facts.jsonl`.
* **Path:** `/media/mark/TG_2TB/Apollo/Project-Apollo/tools/liara_indexer.py`
* **How to Start:** 
  ```bash
  python3 /media/mark/TG_2TB/Apollo/Project-Apollo/tools/liara_indexer.py
  ```
* **How to Stop:** Find the process and kill it, or close the terminal running it.
* **Dependencies:** Requires Ollama running the `liara` model on localhost.

### B. The Open WebUI Memory Bridge (`webui_memory_bridge.py`)
* **What it does:** Sits between Open WebUI and your 35B model. When you type a message in Open WebUI, this script intercepts it, reads the 10 most recent facts from `apollo_facts.jsonl`, secretly pastes those facts into the invisible System Prompt, and forwards it to the 35B model.
* **Path:** `/media/mark/TG_2TB/Apollo/Project-Apollo/webui_memory_bridge.py`
* **How to Start:**
  ```bash
  source /media/mark/TG_2TB/Apollo/Project-Apollo/venv/bin/activate
  uvicorn webui_memory_bridge:app --host 0.0.0.0 --port 8085
  ```
* **How to Stop:** Press `Ctrl+C` in the terminal where it's running, or run `kill -9 $(lsof -t -i:8085)`.

---

## 🌐 2. User Interfaces

### A. Open WebUI (Native)
* **What it does:** The ChatGPT-like frontend for your local models. It handles UI, document uploads (RAG), and standard chat history.
* **Access URL:** `http://localhost:3000`
* **How to Start:** `open-webui serve` (if installed natively via pip)
* **How to Route through Memory Bridge:** Go to Open WebUI > Settings > Connections. Add a new OpenAI Connection URL: `http://localhost:8085/v1` and leave the key empty.

---

## 🛑 How to Fix Things When They Break

* **"The AI forgot everything!"** -> Check if `webui_memory_bridge.py` is running on Port 8085. Check if Open WebUI is pointed to Port 8085. Check `data/apollo_facts.jsonl` to ensure facts actually exist.
* **"Open WebUI says 'Connection Refused'"** -> Either `llama-server` (Port 8082) or `webui_memory_bridge` (Port 8085) has crashed. Restart them using the commands above.
* **"VRAM is instantly crashing (OOM)!"** -> You probably sent too much chat history. Go into Open WebUI Settings > Advanced > Context Length and hard-cap it to 8192 to force old messages to drop.

*(AI Agents: Do not create a new script without documenting it here first.)*