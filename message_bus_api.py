import uvicorn
import threading
import time
import setproctitle
from contextlib import asynccontextmanager

setproctitle.setproctitle("apollo-message-bus")
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, Optional
import asyncio
from fastapi.responses import StreamingResponse

import os
from modules.message_bus import SovereignMessageBus
from modules.sovereign_search import sovereign_search, index_document
from transformers import pipeline
import tarfile
import tempfile
import io

import torch
import gc

# Dynamic Privacy Filter Configuration
pf_config = {"enabled": True, "device": "cpu"}
privacy_filter = None

def load_privacy_filter():
    global privacy_filter, pf_config
    if privacy_filter is not None:
        print("Unloading previous Privacy Filter...", flush=True)
        del privacy_filter
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        privacy_filter = None
    
    if not pf_config["enabled"]:
        print("Privacy Filter is disabled.", flush=True)
        return
        
    print(f"Loading 1.5B Privacy Filter on {pf_config['device'].upper()}...", flush=True)
    try:
        device_id = 0 if pf_config["device"] == "cuda" and torch.cuda.is_available() else -1
        privacy_filter = pipeline(task="token-classification", model="openai/privacy-filter", trust_remote_code=True, device=device_id)
    except Exception as e:
        print(f"Failed to load Privacy Filter: {e}", flush=True)
        privacy_filter = None

# Initial load (defaults to CPU as configured above)
load_privacy_filter()

def scrub_text(text: str) -> str:
    if not privacy_filter or not text:
        return text
    try:
        results = privacy_filter(text)
        if not results:
            return text
        
        merged = []
        for ent in sorted(results, key=lambda x: x['start']):
            if merged and ent['start'] <= merged[-1]['end']:
                merged[-1]['end'] = max(merged[-1]['end'], ent['end'])
            else:
                merged.append(ent)
                
        redacted_text = text
        for entity in reversed(merged):
            start = entity['start']
            end = entity['end']
            redacted_text = redacted_text[:start] + "[REDACTED]" + redacted_text[end:]
        return redacted_text
    except Exception:
        return text

db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data/message_bus.db")
bus = SovereignMessageBus(db_path)

def timeout_checker(bus: SovereignMessageBus, interval: int = 60, timeout_minutes: int = 15):
    """Periodically scans for and resets stalled tasks."""
    while True:
        try:
            bus.reset_stalled_tasks(timeout_minutes=timeout_minutes)
        except Exception as e:
            print(f"Error in timeout_checker: {e}")
        time.sleep(interval)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start the timeout checker thread in the background
    thread = threading.Thread(target=timeout_checker, args=(bus,), daemon=True)
    thread.start()
    yield

app = FastAPI(title="Sovereign Message Bus API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

import json

telemetry_clients = []
task_event_clients = []

class LogRequest(BaseModel):
    node_name: str
    log_line: str

@app.post("/swarm/log")
async def post_swarm_log(req: LogRequest):
    safe_log_line = scrub_text(req.log_line) if req.log_line else req.log_line
    message = f"data: [{req.node_name}] {safe_log_line}\n\n"
    for q in telemetry_clients:
        await q.put(message)
    return {"status": "ok"}

@app.get("/tasks/stream")
async def stream_tasks():
    print("New client connected to /tasks/stream")
    q = asyncio.Queue()
    task_event_clients.append(q)
    async def event_generator():
        try:
            while True:
                try:
                    msg = await asyncio.wait_for(q.get(), timeout=15.0)
                    yield msg
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        except asyncio.CancelledError:
            print("Client disconnected from /tasks/stream")
            if q in task_event_clients:
                task_event_clients.remove(q)
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.get("/swarm/stream")
async def stream_telemetry():
    print("New client connected to /swarm/stream")
    q = asyncio.Queue()
    telemetry_clients.append(q)
    async def event_generator():
        yield "data: [System] Connected to Sovereign Swarm Telemetry\n\n"
        try:
            while True:
                try:
                    # Wait for message with 15s timeout
                    msg = await asyncio.wait_for(q.get(), timeout=15.0)
                    yield msg
                except asyncio.TimeoutError:
                    # Send keep-alive ping
                    yield ": keepalive\n\n"
        except asyncio.CancelledError:
            print("Client disconnected from /swarm/stream")
            if q in telemetry_clients:
                telemetry_clients.remove(q)
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.get("/config/swarm/profiles/{name}")
def get_swarm_profile(name: str):
    try:
        profile = bus.get_swarm_profile(name)
        if profile is None:
            raise HTTPException(status_code=404, detail="Profile not found in database")
        return {"profile": profile}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/config/swarm/presets/{model_name}")
def get_model_preset(model_name: str):
    try:
        preset = bus.get_model_preset(model_name)
        if preset is None:
            raise HTTPException(status_code=404, detail="Preset not found in database")
        return {"preset": preset}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class SetProfileRequest(BaseModel):
    config: Dict[str, Any]

@app.post("/config/swarm/profiles/{name}")
def set_swarm_profile(name: str, req: SetProfileRequest):
    try:
        bus.set_swarm_profile(name, req.config)
        return {"status": "ok", "message": f"Profile '{name}' updated successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/config/swarm/prompts/{name}")
def get_swarm_prompt(name: str):
    try:
        prompt = bus.get_swarm_prompt(name)
        if prompt is None:
            raise HTTPException(status_code=404, detail="Prompt not found in database")
        return {"prompt": prompt}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class SetPromptRequest(BaseModel):
    prompt_text: str

@app.post("/config/swarm/prompts/{name}")
def set_swarm_prompt(name: str, req: SetPromptRequest):
    try:
        bus.set_swarm_prompt(name, req.prompt_text)
        return {"status": "ok", "message": f"Prompt '{name}' updated successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class ScratchpadWriteRequest(BaseModel):
    key: str
    value: str

@app.post("/scratchpad")
def write_scratchpad(req: ScratchpadWriteRequest):
    try:
        bus.write_scratchpad(req.key, req.value)
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/scratchpad/{key}")
def read_scratchpad(key: str):
    try:
        value = bus.read_scratchpad(key)
        if value is None:
            raise HTTPException(status_code=404, detail="Key not found in scratchpad")
        return {"value": value}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class PublishRequest(BaseModel):
    task_name: str
    requirements: Dict[str, Any]
    payload: str

class ClaimRequest(BaseModel):
    node_name: str
    node_capabilities: Dict[str, Any]

class CompleteRequest(BaseModel):
    task_id: str
    result_payload: str
    success: bool = True
    error_trace: Optional[str] = None

class ProposeSkillRequest(BaseModel):
    title: str
    tldr: str
    token_impact: int
    raw_payload: str

class UpdateSkillStatusRequest(BaseModel):
    status: str

@app.post("/memory/proposed")
def propose_skill(req: ProposeSkillRequest):
    try:
        skill_id = bus.propose_skill(req.title, req.tldr, req.token_impact, req.raw_payload)
        return {"status": "ok", "skill_id": skill_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/memory/inbox")
def get_memory_inbox(status: str = 'pending'):
    try:
        skills = bus.list_proposed_skills(status)
        return {"skills": skills}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

import re

@app.post("/memory/proposed/{skill_id}/status")
def update_skill_status(skill_id: int, req: UpdateSkillStatusRequest):
    try:
        if req.status == 'approved':
            skill = bus.get_proposed_skill(skill_id)
            if skill:
                # Format safe filename
                safe_title = re.sub(r'[^a-zA-Z0-9_\-]', '_', skill['title'].lower())
                file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vault", "skills", f"{safe_title}.md")
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(skill['raw_payload'])
                
                # Index into Hybrid Search (ChromaDB + SQLite FTS5)
                index_document(file_path, skill['raw_payload'])
                print(f"[+] Approved and indexed skill: {file_path}")

        bus.update_proposed_skill_status(skill_id, req.status)
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class HeartbeatRequest(BaseModel):
    node_id: str
    status: str
    active_model_archetype: Optional[str] = "any"
    max_slot_context: Optional[int] = 8192
    hot_kv_tokens: Optional[int] = 0
    warm_kv_tokens: Optional[int] = 0
    kv_precision: Optional[str] = "fp16"
    catalog_url: Optional[str] = None

@app.post("/node/heartbeat")
def node_heartbeat(req: HeartbeatRequest, request: Request):
    try:
        endpoint = f"http://{request.client.host}:8082/v1"
        absolute_catalog_url = f"http://{request.client.host}:3000{req.catalog_url}" if req.catalog_url else None
        
        bus.record_heartbeat(
            req.node_id, 
            req.status, 
            req.active_model_archetype, 
            req.max_slot_context, 
            req.hot_kv_tokens, 
            req.warm_kv_tokens, 
            req.kv_precision,
            endpoint,
            absolute_catalog_url
        )
        
        import hashlib
        try:
            hasher = hashlib.md5()
            with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "worker_daemon.py"), "rb") as f:
                hasher.update(f.read())
            core_version = hasher.hexdigest()
        except Exception:
            core_version = None
            
        return {"status": "ok", "core_version": core_version}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/node/status")
def get_node_status():
    try:
        fleet = bus.get_fleet_status()
        return {"fleet": fleet}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/tasks/publish")
def publish_task(req: PublishRequest):
    task_id = bus.publish_task(req.task_name, req.requirements, req.payload)
    return {"task_id": task_id}

@app.post("/tasks/claim")
def claim_task(req: ClaimRequest):
    task = bus.claim_task(req.node_name, req.node_capabilities)
    if task:
        return {"task": task}
    return {"task": None}

class ReleaseRequest(BaseModel):
    task_id: str

@app.post("/tasks/release")
def release_task(req: ReleaseRequest):
    bus.release_task(req.task_id)
    return {"status": "ok"}

@app.post("/tasks/complete")
async def complete_task(req: CompleteRequest):
    safe_result_payload = scrub_text(req.result_payload) if req.result_payload else req.result_payload
    safe_error_trace = scrub_text(req.error_trace) if req.error_trace else req.error_trace
    
    bus.complete_task(req.task_id, safe_result_payload, req.success, safe_error_trace)

    moe_routing_map = None
    if safe_result_payload:
        try:
            parsed = json.loads(safe_result_payload)
            if isinstance(parsed, dict) and "moe_routing_map" in parsed:
                moe_routing_map = parsed["moe_routing_map"]
        except Exception:
            pass

    # Broadcast the completion event
    event_data = json.dumps({
        "task_id": req.task_id,
        "status": "completed" if req.success else "failed",
        "error_trace": safe_error_trace,
        "moe_routing_map": moe_routing_map
    })
    message = f"data: {event_data}\n\n"
    for q in task_event_clients:
        await q.put(message)
        
    return {"status": "success"}

class AbortRequest(BaseModel):
    task_id: str

@app.post("/tasks/abort")
async def abort_task(req: AbortRequest):
    bus.abort_task(req.task_id)
    
    # Broadcast the abort event
    event_data = json.dumps({
        "task_id": req.task_id,
        "status": "aborted"
    })
    message = f"data: {event_data}\n\n"
    for q in task_event_clients:
        await q.put(message)
        
    return {"status": "success"}

@app.get("/tasks/{task_id}")
def check_status(task_id: str):
    task = bus.check_task_status(task_id)
    if task:
        return {"task": task}
    raise HTTPException(status_code=404, detail="Task not found")

class PFConfigRequest(BaseModel):
    enabled: bool
    device: str

@app.get("/system/privacy_filter")
def get_pf_config():
    return pf_config

@app.post("/system/privacy_filter")
def set_pf_config(req: PFConfigRequest):
    global pf_config
    pf_config["enabled"] = req.enabled
    pf_config["device"] = req.device
    load_privacy_filter()
    return pf_config

class FastContextConfigRequest(BaseModel):
    enabled: bool

@app.get("/system/fastcontext")
def get_fastcontext_config():
    try:
        active_profile = bus.get_swarm_profile("codebase_investigator")
        if not active_profile:
            return {"enabled": False}
        return {"enabled": active_profile.get("model", "").startswith("FastContext")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/system/fastcontext")
def set_fastcontext_config(req: FastContextConfigRequest):
    try:
        if req.enabled:
            profile_data = bus.get_swarm_profile("codebase_investigator_fastcontext")
        else:
            profile_data = bus.get_swarm_profile("codebase_investigator_qwen")
            
        if not profile_data:
            raise HTTPException(status_code=500, detail="Base profile not found in DB")
            
        bus.set_swarm_profile("codebase_investigator", profile_data)
        
        # Keep YAML in sync so it doesn't get overwritten by sync_profiles.py later
        import yaml
        yaml_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profiles.yaml")
        if os.path.exists(yaml_path):
            with open(yaml_path, 'r') as f:
                data = yaml.safe_load(f) or {}
            
            if req.enabled:
                if 'codebase_investigator_fastcontext' in data:
                    data['codebase_investigator'] = data['codebase_investigator_fastcontext']
            else:
                if 'codebase_investigator_qwen' in data:
                    data['codebase_investigator'] = data['codebase_investigator_qwen']
                
            with open(yaml_path, 'w') as f:
                yaml.dump(data, f, sort_keys=False)
                
        return {"status": "ok", "enabled": req.enabled}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class SearchRequest(BaseModel):
    query: str
    n_results: Optional[int] = 2

@app.post("/memory/search")
def search_memory(req: SearchRequest):
    try:
        results = sovereign_search(req.query, req.n_results)
        return {"results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/sync/bundle.tar.gz")
def get_sync_bundle():
    """Generates a real-time tar.gz bundle of the Apollo core files for worker nodes to auto-update."""
    import subprocess
    import tempfile
    from fastapi.responses import FileResponse
    from starlette.background import BackgroundTask
    
    root_dir = os.path.dirname(os.path.abspath(__file__))
    fd, temp_path = tempfile.mkstemp(suffix=".tar.gz")
    os.close(fd)
    
    # Exclude heavy/unnecessary directories
    excludes = [
        "--exclude=.git", "--exclude=venv", "--exclude=venv_cachyos", 
        "--exclude=node_modules", "--exclude=archive", "--exclude=models", 
        "--exclude=data", "--exclude=chat_history", "--exclude=legacy_vault", 
        "--exclude=logs", "--exclude=run", "--exclude=llama.cpp", "--exclude=whisper.cpp",
        "--exclude=*.gguf", "--exclude=*.bin", "--exclude=__pycache__", "--exclude=.env"
    ]
    
    cmd = ["tar", "-czf", temp_path] + excludes + ["-C", root_dir, "."]
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        os.remove(temp_path)
        raise HTTPException(status_code=500, detail=f"Failed to create bundle: {e}")
        
    def cleanup():
        if os.path.exists(temp_path):
            os.remove(temp_path)
            
    return FileResponse(temp_path, media_type="application/gzip", filename="apollo_bundle.tar.gz", background=BackgroundTask(cleanup))

@app.get("/deploy")
def get_deploy_script(request: Request):
    """Serves the Tailscale-style bash installer for worker nodes."""
    api_ip = request.client.host
    host_url = f"http://{request.url.hostname}:{request.url.port}"
    
    script = f"""#!/usr/bin/env bash
set -e

echo "============================================="
echo "🚀 Apollo Sovereign Worker Node Installer"
echo "============================================="

# Ensure dependencies
if ! command -v python3 &> /dev/null || ! command -v npm &> /dev/null; then
    echo "[!] Missing dependencies. Please install python3 and npm first."
    exit 1
fi

# Allow passing via environment variables, otherwise prompt via /dev/tty
if [ -z "$NODE_NAME" ]; then
    read -p "Enter Node Name (e.g. Apollo-Worker-Beta): " NODE_NAME </dev/tty
fi
if [ -z "$NODE_NAME" ]; then
    echo "Node Name is required."
    exit 1
fi

if [ -z "$API_URL" ]; then
    read -p "Enter Message Bus API URL [default: {host_url}]: " API_URL </dev/tty
fi
API_URL=${{API_URL:-{host_url}}}

echo "[*] Setting up Apollo in ~/.apollo..."
INSTALL_DIR="$HOME/.apollo"
mkdir -p "$INSTALL_DIR"

echo "[*] Downloading core bundle from Message Bus..."
curl -sL "$API_URL/sync/bundle.tar.gz" | tar -xz -C "$INSTALL_DIR"

echo "[*] Setting up Python virtual environment..."
cd "$INSTALL_DIR"
python3 -m venv venv
./venv/bin/pip install --upgrade pip
if [ -f requirements.txt ]; then
    ./venv/bin/pip install -r requirements.txt
fi

echo "[*] Setting up Node.js dependencies..."
if [ -d "engines/open-multi-agent" ]; then
    cd engines/open-multi-agent
    npm install
    cd ../..
fi

echo "[*] Creating systemd service..."
SERVICE_FILE="$HOME/.config/systemd/user/apollo-worker.service"
mkdir -p "$HOME/.config/systemd/user"

cat <<EOF > "$SERVICE_FILE"
[Unit]
Description=Apollo Sovereign Worker Daemon
After=network.target

[Service]
Type=simple
WorkingDirectory=$INSTALL_DIR
Environment="MESSAGE_BUS_API=$API_URL"
Environment="NODE_NAME=$NODE_NAME"
Environment="APOLLO_ROOT=$INSTALL_DIR"
ExecStartPre=-/usr/bin/curl -sL $API_URL/sync/bundle.tar.gz -o /tmp/apollo_bundle.tar.gz
ExecStartPre=-/bin/tar -xz -C $INSTALL_DIR -f /tmp/apollo_bundle.tar.gz
ExecStart=$INSTALL_DIR/venv/bin/python3 $INSTALL_DIR/worker_daemon.py
Restart=always
RestartSec=10

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user enable apollo-worker.service
systemctl --user restart apollo-worker.service
loginctl enable-linger $USER

echo "============================================="
echo "✅ Installation Complete!"
echo "Service is running as a user systemd daemon."
echo "Check status: systemctl --user status apollo-worker"
echo "View logs: journalctl --user -fu apollo-worker"
echo "============================================="
"""
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(script)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
