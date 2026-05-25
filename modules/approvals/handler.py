import json
import os
import time
import uuid
import subprocess

# Use absolute path relative to the module's location
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PENDING_PATH = os.path.join(CURRENT_DIR, "pending.json")

# Core files that ALWAYS require approval for write_code
CORE_FILES = [
    "buddy_agent.py",
    "llm_interface.py",
    "modules/",
    ".zshrc",
    ".bashrc",
    "GEMINI.md",
    "SOUL.md"
]

def should_require_approval(action_name, params):
    """
    Heuristic to determine if an action requires human intervention.
    """
    if action_name == "run_shell":
        return True # Shell commands are always risky
    
    if action_name == "write_code":
        try:
            # Parse params if it's a string representation of a dict
            if isinstance(params, str):
                try:
                    p = eval(params)
                except:
                    p = {}
            else:
                p = params
                
            file_path = p.get("file_path", "")
            content = p.get("content", "")
            
            # 1. Core File Protection
            if any(core in file_path for core in CORE_FILES):
                return True
            
            # 2. Large File Protection (> 50 lines or > 2000 chars)
            if content.count("\n") > 50 or len(content) > 2000:
                return True
            
            # 3. New File Heuristic: Auto-allow new non-core files
            if not os.path.exists(file_path):
                return False
                
            return False # Default to auto-allow for small, non-core edits
        except:
            return True # If parsing fails, be safe
            
    return False

def request_approval(action_name, params, thought_trace=""):
    """
    Adds an action to the pending queue and waits for it to be approved or denied.
    Prioritizes the Level 3 Logic Inspector (GUI) if available.
    """
    # check Heuristic
    if not should_require_approval(action_name, params):
        return True, params

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
        "posted": False,
        "timestamp": time.time()
    }

    with open(PENDING_PATH, 'w') as f:
        json.dump(queue, f, indent=4)

    # Level 3: Logic Inspector (PyQt6 GUI)
    if os.environ.get("DISPLAY"):
        try:
            from modules.approvals.inspector import launch_inspector
            res, edited_params = launch_inspector(action_name, str(params), thought_trace)
            
            # Clean up immediately
            if os.path.exists(PENDING_PATH):
                with open(PENDING_PATH, 'r') as f:
                    current_queue = json.load(f)
                    if approval_id in current_queue:
                        del current_queue[approval_id]
                        with open(PENDING_PATH, 'w') as f:
                            json.dump(current_queue, f, indent=4)
            
            if res == "approved":
                return True, edited_params
            else:
                return False, params
        except Exception as e:
            # Fallback to KDialog if PyQt fails
            try:
                msg = f"Apollo wants to run: {action_name}\n\nParams: {params}\n\nProceed?"
                cmd = ["kdialog", "--title", "Apollo Security Intercept", "--yesno", msg]
                k_res = subprocess.run(cmd, timeout=30)
                if k_res.returncode == 0:
                    return True, params
                return False, params
            except:
                pass

    # Audible Alert (Background fallback)
    subprocess.Popen(["canberra-gtk-play", "-i", "message-new-instant"], stderr=subprocess.DEVNULL)

    print(f"\n[⚠️  PENDING APPROVAL]: {action_name} (ID: {approval_id})")
    print(f"[PARAMS]: {params}")
    print(f"[HINT]: Set 'status': 'approved' for ID {approval_id} in {PENDING_PATH}")

    # Polling Fallback
    timeout = 300 
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
                            del current_queue[approval_id]
                            with open(PENDING_PATH, 'w') as f:
                                json.dump(current_queue, f, indent=4)
                            return True, params
                        elif status == "denied":
                            del current_queue[approval_id]
                            with open(PENDING_PATH, 'w') as f:
                                json.dump(current_queue, f, indent=4)
                            return False, params
                except:
                    continue
    
    return False, params # Timeout
