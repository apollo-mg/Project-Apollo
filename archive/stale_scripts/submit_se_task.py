import urllib.request
import urllib.parse
import json
import time
import sys

payload = {
    "task_name": "software_engineering",
    "requirements": {
        "target_node": "lead_architect",
        "min_context": 8192,
        "min_precision": 4.0,
        "requires_internet": False,
        "profile": "software_engineer"
    },
    "payload": """Engineering Goal: Build the Starbuck Dependency Resolver using the 'Subagent Routing' architecture (Option 2).
Requirements:
1. Modify /mnt/TG_2TB/Projects/Apollo/profiles.yaml to define a new subagent profile named 'starbuck_resolver'. Give it strict system instructions on how to analyze apt/pacman failures, read logs, and formulate bash commands to fix broken package states.
2. IMPORTANT: Avoid the 'ghost profile' trap. You MUST add 'starbuck_resolver' to the 'allowed_tools' array under the main 'architect' profile in /mnt/TG_2TB/Projects/Apollo/profiles.yaml.
3. Modify /mnt/TG_2TB/Projects/Apollo/starbuck_daemon.py to add a new FastMCP tool named 'starbuck_execute_fix' that accepts raw bash commands to resolve dependencies. This tool MUST be gated at YOLO Level 3.
Context: Keep the Python daemon strictly as 'The Hands' and use the orchestrator as 'The Brain'.
Test Command: None"""
}

try:
    req = urllib.request.Request("http://127.0.0.1:8000/tasks/publish", data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'})
    res = urllib.request.urlopen(req)
    data = json.loads(res.read().decode('utf-8'))
    task_id = data['task_id']
    print(f"Task {task_id} queued to Sovereign Message Bus.")

    while True:
        time.sleep(5)
        res = urllib.request.urlopen(f"http://127.0.0.1:8000/tasks/{task_id}")
        data = json.loads(res.read().decode('utf-8'))
        task = data.get('task')
        if task and task['status'] == 'completed':
            print("\n--- Remote Engineering Report ---")
            print(task['output_payload'])
            break
        elif task and task['status'] == 'failed':
            print("\n--- Remote Engineering Failed ---")
            print(task['output_payload'])
            break
        elif task and task['status'] == 'in_progress':
            sys.stdout.write('R') # Running
            sys.stdout.flush()
        else:
            sys.stdout.write('Q') # Queued
            sys.stdout.flush()
except Exception as e:
    print(f"Error: {e}")