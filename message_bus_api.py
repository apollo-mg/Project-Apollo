import uvicorn
import threading
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, Optional
import asyncio
from fastapi.responses import StreamingResponse

import os
from modules.message_bus import SovereignMessageBus
from modules.sovereign_search import sovereign_search

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
    message = f"data: [{req.node_name}] {req.log_line}\n\n"
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

@app.get("/config/profiles")
def get_profiles():
    profiles_path = os.environ.get("PROFILES_PATH", "/app/profiles.yaml")
    if not os.path.exists(profiles_path):
        raise HTTPException(status_code=404, detail="Profiles config not found on message bus")
    try:
        with open(profiles_path, "r") as f:
            return {"yaml": f.read()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/config/context")
def get_context():
    context_path = os.environ.get("CONTEXT_PATH", "/app/LOCAL_AGENT_CONTEXT.md")
    if not os.path.exists(context_path):
        return {"markdown": ""}
    try:
        with open(context_path, "r") as f:
            return {"markdown": f.read()}
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
    task_id: int
    result_payload: str
    success: bool = True

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

@app.post("/memory/proposed/{skill_id}/status")
def update_skill_status(skill_id: int, req: UpdateSkillStatusRequest):
    try:
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

@app.post("/node/heartbeat")
def node_heartbeat(req: HeartbeatRequest):
    try:
        bus.record_heartbeat(
            req.node_id, 
            req.status, 
            req.active_model_archetype, 
            req.max_slot_context, 
            req.hot_kv_tokens, 
            req.warm_kv_tokens, 
            req.kv_precision
        )
        return {"status": "ok"}
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

@app.post("/tasks/complete")
async def complete_task(req: CompleteRequest):
    bus.complete_task(req.task_id, req.result_payload, req.success)
    
    # Broadcast the completion event
    event_data = json.dumps({
        "task_id": req.task_id,
        "status": "completed" if req.success else "failed"
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
def check_status(task_id: int):
    task = bus.check_task_status(task_id)
    if task:
        return {"task": task}
    raise HTTPException(status_code=404, detail="Task not found")

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

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
