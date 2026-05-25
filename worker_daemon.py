#!/usr/bin/env python3
import time
import sys
import os
import json
import logging
import subprocess

# Ensure we can import from the Apollo root
APOLLO_ROOT = os.environ.get("APOLLO_ROOT", os.path.dirname(os.path.abspath(__file__)))
sys.path.append(APOLLO_ROOT)

try:
    from modules.message_bus import SovereignMessageBus, RemoteMessageBus
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
    
    engine_dir = os.path.join(APOLLO_ROOT, "engines", "open-multi-agent-upstream")
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
        
        if process.returncode == 0:
            return "".join(output_payload)
        else:
            raise RuntimeError(f"Apollo CLI exited with code {process.returncode}:\n{''.join(output_payload)}")
    except subprocess.TimeoutExpired:
        process.kill()
        raise RuntimeError("Task execution timed out after 15 minutes.")
    except Exception as e:
        raise RuntimeError(f"Failed to execute Apollo CLI: {e}")

def main():
    logger.info(f"Starting Worker Daemon: {NODE_NAME}")
    logger.info(f"Node Physics: {NODE_CAPABILITIES}")
    
    api_url = os.environ.get("MESSAGE_BUS_API")
    if api_url:
        logger.info(f"Connecting to Sovereign Message Bus API at: {api_url}")
        bus = RemoteMessageBus(api_url)
    else:
        default_db_path = os.path.join(APOLLO_ROOT, "data", "message_bus.db")
        db_path = os.environ.get("DB_PATH", default_db_path)
        logger.info(f"Connecting to Local Message Bus Database at: {db_path}")
        bus = SovereignMessageBus(db_path)
    
    logger.info("Listening for tasks on the Sovereign Message Bus...")
    
    while True:
        try:
            # Attempt to claim a task that fits this node's physics
            claimed_task = bus.claim_task(NODE_NAME, NODE_CAPABILITIES)
            
            if claimed_task:
                task_id = claimed_task["id"]
                logger.info(f"Claimed Task #{task_id}: {claimed_task['task_name']}")
                
                try:
                    # Execute it
                    result_payload = execute_task(claimed_task)
                    
                    # Mark it completed
                    bus.complete_task(task_id, result_payload=result_payload, success=True)
                    logger.info(f"Task #{task_id} marked as COMPLETED.")
                    
                except Exception as e:
                    logger.error(f"Task #{task_id} failed during execution: {e}")
                    bus.complete_task(task_id, result_payload=str(e), success=False)
                    
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