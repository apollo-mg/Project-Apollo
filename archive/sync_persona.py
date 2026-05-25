import os
import subprocess
import json
from datetime import datetime

# Configuration
WORKSTATION_IP = "10.0.0.118"
WORKSTATION_USER = "gemini"
PROJECT_ROOTS = {
    "apollo": "/home/gemini/Project-Apollo",
    "omni": "/home/gemini/Project-Apollo" # Currently both in same root
}
SYNC_MANIFEST = os.path.expanduser("~/.gemini/sovereign_manifest.json")

def run_remote(command):
    try:
        result = subprocess.run(
            ["sshpass", "-p", "apollo", "ssh", "-o", "StrictHostKeyChecking=no", 
             f"{WORKSTATION_USER}@{WORKSTATION_IP}", command],
            capture_output=True, text=True, timeout=15
        )
        return result.stdout.strip()
    except Exception as e:
        return f"Error: {e}"

def get_latest_context(project_name):
    path = PROJECT_ROOTS.get(project_name)
    if not path:
        return None
    
    print(f"[*] Fetching latest context for {project_name} from {WORKSTATION_IP}...")
    
    # Get MD5 and ModTime of core files
    files = ["MEMORY.md", "ROADMAP.md", "SOUL.md"]
    manifest = {"project": project_name, "timestamp": datetime.now().isoformat(), "files": {}}
    
    for f in files:
        remote_path = f"{path}/{f}"
        stat = run_remote(f"stat -c %Y {remote_path} 2>/dev/null")
        if "Error" not in stat and stat:
            manifest["files"][f] = {"mod_time": stat, "remote_path": remote_path}
            
    return manifest

def sync_all():
    global_manifest = {}
    for proj in PROJECT_ROOTS:
        m = get_latest_context(proj)
        if m:
            global_manifest[proj] = m
            
    with open(SYNC_MANIFEST, 'w') as f:
        json.dump(global_manifest, f, indent=2)
    print(f"[+] Global Persona Manifest updated at {SYNC_MANIFEST}")

if __name__ == "__main__":
    sync_all()
