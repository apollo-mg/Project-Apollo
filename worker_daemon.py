#!/usr/bin/env python3
import time
import sys
import os
import json
import logging
import subprocess
import setproctitle

# Ensure we can import from the Apollo root
APOLLO_ROOT = os.environ.get("APOLLO_ROOT", os.path.dirname(os.path.abspath(__file__)))
sys.path.append(APOLLO_ROOT)

NODE_NAME = os.environ.get("NODE_NAME", "apollo-worker")
setproctitle.setproctitle(NODE_NAME)

try:
    from modules.message_bus import SovereignMessageBus, MessageBusClient
except ModuleNotFoundError:
    print(f"CRITICAL ERROR: Could not find 'modules.message_bus'. Ensure APOLLO_ROOT is set correctly. Currently: {APOLLO_ROOT}")
    sys.exit(1)

logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - [%(levelname)s] %(name)s: %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("WorkerDaemon")

# ---------------------------------------------------------------------------
# Node Capability Configuration (Hardware Physics)
# ---------------------------------------------------------------------------
# These would typically be set via ENV vars on the specific hardware node.
# Defaults here are set for a robust node (like the P100 or RX 9070).
NODE_NAME = os.environ.get("NODE_NAME", "Apollo-Worker-Alpha")
NODE_ROLE = os.environ.get("NODE_ROLE", "any") # 'sprint_executor' or 'lead_architect' or 'any'
CONTEXT_WINDOW = int(os.environ.get("CONTEXT_WINDOW", "32768"))
PRECISION_BITS = float(os.environ.get("PRECISION_BITS", "4.0"))
INTERNET_ACCESS = os.environ.get("INTERNET_ACCESS", "true").lower() in ("true", "1", "yes")

NODE_CAPABILITIES = {
    "node_role": NODE_ROLE,
    "context_window": CONTEXT_WINDOW,
    "precision_bits": PRECISION_BITS,
    "internet_access": INTERNET_ACCESS
}

def execute_task(task: dict) -> str:
    """
    Executes the claimed task.
    This is where the daemon routes the payload to the actual LLM engine.
    """
    import tempfile
    
    task_id = task.get("id")
    task_name = task.get("task_name", "unknown")
    payload = task.get("input_payload", "")
    
    # Parse requirements to figure out which profile to use
    reqs_str = task.get("requirements_json", "{}")
    try:
        reqs = json.loads(reqs_str)
    except json.JSONDecodeError:
        reqs = {}
        
    # Heuristic: use 'profile' key if provided, else fallback to mapping 'target_node'
    profile_name = reqs.get("profile")
    if not profile_name:
        target_node = reqs.get("target_node", "any")
        if target_node == "sprint_executor":
            profile_name = "software_engineer"
        elif target_node == "lead_architect":
            profile_name = "architect"
        else:
            profile_name = "architect" # Default safe profile

    logger.info(f"Executing task '{task_name}' (ID: {task_id}) using profile: '{profile_name}'")
    
    engine_dir = os.path.join(APOLLO_ROOT, "engines", "open-multi-agent")
    cmd = ["npx", "--yes", "tsx", "examples/apollo_cli.ts", "--profile", profile_name, "-p", payload]
    logger.info(f"Running command: {' '.join(cmd)}")
    
    import threading
    import queue
    import urllib.request
    
    log_queue = queue.Queue()
    api_url = os.environ.get("MESSAGE_BUS_API", "http://127.0.0.1:8000")
    
    def log_worker():
        while True:
            item = log_queue.get()
            if item is None: break
            try:
                req = urllib.request.Request(
                    f"{api_url}/swarm/log",
                    data=json.dumps(item).encode('utf-8'),
                    headers={'Content-Type': 'application/json'}
                )
                urllib.request.urlopen(req, timeout=1)
            except Exception:
                pass
                
    t = threading.Thread(target=log_worker, daemon=True)
    t.start()
    
    import pty
    master_fd, slave_fd = pty.openpty()
    
    try:
        process = subprocess.Popen(
            cmd,
            stdout=slave_fd,
            stderr=slave_fd,
            text=False,
            cwd=engine_dir,
            env={**os.environ, "FORCE_COLOR": "1"}
        )
        os.close(slave_fd) # Close slave in parent so master gets EOF when child exits
        
        output_payload = []
        import io
        import errno
        with os.fdopen(master_fd, 'r', encoding='utf-8', errors='replace') as stdout:
            while True:
                try:
                    line = stdout.readline()
                except OSError as e:
                    if e.errno == errno.EIO: # [Errno 5] Input/output error
                        break
                    raise
                if not line: break
                sys.stdout.write(line)
                sys.stdout.flush()
                output_payload.append(line)
                clean_line = line.rstrip('\r\n')
                log_queue.put({"node_name": NODE_NAME, "log_line": clean_line})
                
        process.wait(timeout=900)
        log_queue.put(None) # stop worker
        
        full_output = "".join(output_payload)
        if process.returncode == 0:
            return full_output, None
        else:
            return None, full_output
    except subprocess.TimeoutExpired:
        process.kill()
        return None, "RuntimeError: Task execution timed out after 15 minutes."
    except Exception as e:
        return None, f"RuntimeError: Failed to execute Apollo CLI: {e}"

def main():
    logger.info(f"Starting Worker Daemon: {NODE_NAME}")
    logger.info(f"Node Physics: {NODE_CAPABILITIES}")
    
    api_url = os.environ.get("MESSAGE_BUS_API")
    if api_url:
        logger.info(f"Connecting to Sovereign Message Bus API at: {api_url}")
        bus = MessageBusClient(api_url)
    else:
        default_db_path = os.path.join(APOLLO_ROOT, "data", "message_bus.db")
        db_path = os.environ.get("DB_PATH", default_db_path)
        logger.info(f"Connecting to Local Message Bus Database at: {db_path}")
        bus = SovereignMessageBus(db_path)
    
    import threading
    import platform

    current_status = "idle"

    def heartbeat_worker():
        import urllib.request
        while True:
            try:
                active_model = "offline"
                max_ctx = CONTEXT_WINDOW
                hot_kv = 0

                # Try to ping the local llama-server for live telemetry
                try:
                    req = urllib.request.Request("http://127.0.0.1:8082/props", method="GET")
                    with urllib.request.urlopen(req, timeout=1) as res:
                        data = json.loads(res.read().decode('utf-8'))
                        
                        model_path = data.get("model_path", "")
                        if model_path:
                            active_model = os.path.basename(model_path)
                        else:
                            active_model = "online"
                            
                        # Extract the actual live context window size loaded into VRAM
                        max_ctx = data.get("default_generation_settings", {}).get("n_ctx", CONTEXT_WINDOW)
                except Exception:
                    pass

                try:
                    req = urllib.request.Request("http://127.0.0.1:8082/health", method="GET")
                    with urllib.request.urlopen(req, timeout=1) as res:
                        data = json.loads(res.read().decode('utf-8'))
                        # llama-server /health sometimes has n_kv_used or we can just send 0 if unavailable
                except Exception:
                    pass

                # Check if NullClaw A2A is enabled
                catalog_url = None
                config_paths = [
                    os.path.expanduser("~/.nullclaw/config.json"),
                    os.path.abspath(os.path.join(os.path.dirname(__file__), "engines", "nullclaw", "config.json")),
                    os.path.abspath(os.path.join(os.path.dirname(__file__), "engines", "nullclaw", ".nullclaw", "config.json"))
                ]
                for config_path in config_paths:
                    if os.path.exists(config_path):
                        try:
                            with open(config_path, 'r') as f:
                                nc_config = json.load(f)
                                if nc_config.get("a2a", {}).get("enabled"):
                                    catalog_url = "/.well-known/agent-card.json"
                                    break
                        except Exception:
                            pass

                bus.record_heartbeat(
                    node_id=NODE_NAME,
                    status=current_status,
                    active_model_archetype=active_model,
                    max_slot_context=max_ctx,
                    hot_kv_tokens=hot_kv,
                    warm_kv_tokens=0,
                    kv_precision="fp16",
                    catalog_url=catalog_url
                )
                
                # Check for state-sync auto-updates (handled by the API returning core_version)
                # We do this directly against the REST API for simplicity
                import urllib.request
                import hashlib
                req = urllib.request.Request(f"{api_url}/node/heartbeat", data=json.dumps({
                    "node_id": NODE_NAME, "status": current_status
                }).encode('utf-8'), headers={'Content-Type': 'application/json'}, method="POST")
                with urllib.request.urlopen(req, timeout=2) as res:
                    data = json.loads(res.read().decode('utf-8'))
                    remote_version = data.get("core_version")
                    
                    if remote_version:
                        hasher = hashlib.md5()
                        try:
                            with open(os.path.abspath(__file__), "rb") as f:
                                hasher.update(f.read())
                            local_version = hasher.hexdigest()
                            
                            if local_version != remote_version:
                                logger.warning(f"State-Sync mismatch! Local: {local_version}, Remote: {remote_version}")
                                logger.warning("Restarting daemon to trigger auto-sync via systemd ExecStartPre...")
                                import os
                                os._exit(0)
                        except Exception as e:
                            logger.error(f"Failed to check local core version: {e}")
                            
            except Exception as e:
                logger.error(f"Heartbeat ping failed: {e}")
            time.sleep(5)

    if hasattr(bus, 'record_heartbeat'):
        t_hb = threading.Thread(target=heartbeat_worker, daemon=True)
        t_hb.start()
        logger.info("Heartbeat telemetry beacon started.")

    logger.info("Listening for tasks on the Sovereign Message Bus...")
    
    while True:
        try:
            # Attempt to claim a task that fits this node's physics
            claimed_task = bus.claim_task(NODE_NAME, NODE_CAPABILITIES)
            
            if claimed_task:
                current_status = "executing_task"
                task_id = claimed_task["id"]
                logger.info(f"Claimed Task #{task_id}: {claimed_task['task_name']}")
                
                try:
                    # Execute it
                    result_payload = execute_task(claimed_task)

                    # Intercept MoE Telemetry
                    telemetry_file = "/tmp/llama_moe_routing.log"
                    if os.path.exists(telemetry_file):
                        try:
                            with open(telemetry_file, "r") as f:
                                lines = f.readlines()
                            open(telemetry_file, "w").close() # Clear file

                            heat_map = {}
                            for line in lines:
                                if line.startswith("[MoE_Telemetry]"):
                                    try:
                                        data = json.loads(line.split("[MoE_Telemetry] ")[1])
                                        layer = str(data["layer"])
                                        if layer not in heat_map:
                                            heat_map[layer] = {}
                                        for exp, count in data["experts"].items():
                                            heat_map[layer][exp] = heat_map[layer].get(exp, 0) + count
                                    except Exception:
                                        pass

                            if heat_map:
                                try:
                                    parsed = json.loads(result_payload)
                                    if isinstance(parsed, dict):
                                        parsed["moe_routing_map"] = heat_map
                                        result_payload = json.dumps(parsed)
                                except Exception:
                                    result_payload = json.dumps({
                                        "raw_output": result_payload,
                                        "moe_routing_map": heat_map
                                    })
                        except Exception as e:
                            logger.error(f"Failed to process MoE telemetry: {e}")

                    # Mark it completed
                    bus.complete_task(task_id, result_payload=result_payload, success=True)
                    logger.info(f"Task #{task_id} marked as COMPLETED.")
                    
                except Exception as e:
                    logger.error(f"Task #{task_id} failed during execution: {e}")
                    bus.complete_task(task_id, result_payload=str(e), success=False)
                finally:
                    current_status = "idle"
                    
            else:
                # No matching tasks pending, wait before polling again
                time.sleep(3)
                
        except KeyboardInterrupt:
            logger.info("Daemon shutting down gracefully...")
            break
        except Exception as e:
            logger.error(f"Unexpected error in daemon loop: {e}")
            time.sleep(5) # Back off on error

if __name__ == "__main__":
    main()