import json
import os
import time
import uuid

# Use absolute path relative to the module's location
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PENDING_PATH = os.path.join(CURRENT_DIR, "pending.json")

def request_approval(action_name, params):
    """
    Adds an action to the pending queue and waits for it to be approved or denied.
    Approval is signaled by setting "status": "approved" in the pending.json file.
    """
    approval_id = str(uuid.uuid4())
    
    # Load existing queue
    if os.path.exists(PENDING_PATH):
        with open(PENDING_PATH, 'r') as f:
            try:
                queue = json.load(f)
            except:
                queue = {}
    else:
        queue = {}

    # Add new request
    queue[approval_id] = {
        "action": action_name,
        "params": params,
        "status": "pending",
        "posted": False, # New flag for external interfaces (Discord)
        "timestamp": time.time()
    }

    with open(PENDING_PATH, 'w') as f:
        json.dump(queue, f, indent=4)

    # Audible Alert
    import subprocess
    subprocess.Popen(["canberra-gtk-play", "-i", "message-new-instant"], stderr=subprocess.DEVNULL)

    print(f"\n[⚠️  PENDING APPROVAL]: {action_name} (ID: {approval_id})")
    print(f"[PARAMS]: {params}")
    print(f"[HINT]: Set 'status': 'approved' for ID {approval_id} in {PENDING_PATH}")

    # Wait for status change (polling for simplicity in this CLI environment)
    # A more robust version would use file watchers (watchdog)
    timeout = 300 # 5 minutes
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        time.sleep(2)
        if os.path.exists(PENDING_PATH):
            with open(PENDING_PATH, 'r') as f:
                try:
                    current_queue = json.load(f)
                    if approval_id in current_queue:
                        status = current_queue[approval_id].get("status")
                        if status == "approved":
                            # Clean up
                            del current_queue[approval_id]
                            with open(PENDING_PATH, 'w') as f:
                                json.dump(current_queue, f, indent=4)
                            return True
                        elif status == "denied":
                            del current_queue[approval_id]
                            with open(PENDING_PATH, 'w') as f:
                                json.dump(current_queue, f, indent=4)
                            return False
                except:
                    continue
    
    return False # Timeout
