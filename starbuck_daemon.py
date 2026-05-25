import os
import subprocess
from typing import List, Optional
import urllib.request
import urllib.parse
import json
from mcp.server.fastmcp import FastMCP

# Initialize the Starbuck MCP Server
mcp = FastMCP("Starbuck")

# YOLO Hierarchy:
# Level 0: Paranoid (Read-only, system info)
# Level 1: Supervised (Read configs)
# Level 2: Trust but Verify (Write configs, require approval to deploy)
# Level 3: Full YOLO (Autonomous package install, deployment)

def get_yolo_level() -> int:
    return int(os.environ.get("STARBUCK_YOLO_LEVEL", "0"))

@mcp.tool()
def system_recon(target: str) -> str:
    """
    Run read-only system reconnaissance commands.
    Allowed targets: 'lspci', 'nvidia-smi', 'rocm-smi', 'df -h', 'free -m', 'ls -la'.
    Requires YOLO Level >= 0 (Always allowed if target is safe).
    """
    safe_commands = ["lspci", "nvidia-smi", "rocm-smi", "df -h", "free -m", "ls -la"]
    
    if target not in safe_commands and not any(target.startswith(cmd) for cmd in safe_commands):
        return f"Error: Command '{target}' is not in the allowed read-only list for Level 0."
        
    try:
        result = subprocess.run(target, shell=True, capture_output=True, text=True, timeout=10)
        output = result.stdout
        if result.stderr:
            output += f"\n--- stderr ---\n{result.stderr}"
        return output
    except Exception as e:
        return f"Error executing recon: {e}"

@mcp.tool()
def read_config(file_path: str) -> str:
    """
    Read a configuration file from the host.
    Requires YOLO Level >= 1.
    """
    if get_yolo_level() < 1:
        return f"Error: YOLO Level {get_yolo_level()} blocks reading system configurations. Need Level 1."
        
    if not os.path.exists(file_path):
        return f"Error: File '{file_path}' does not exist."
        
    try:
        with open(file_path, 'r') as f:
            return f.read()
    except Exception as e:
        return f"Error reading config: {e}"

@mcp.tool()
def write_config(file_path: str, content: str) -> str:
    """
    Write or overwrite a configuration file (e.g., docker-compose.yml).
    Requires YOLO Level >= 2.
    """
    if get_yolo_level() < 2:
        return f"Error: YOLO Level {get_yolo_level()} blocks writing system configurations. Need Level 2."
        
    try:
        with open(file_path, 'w') as f:
            f.write(content)
        return f"Success: Wrote configuration to {file_path}"
    except Exception as e:
        return f"Error writing config: {e}"

@mcp.tool()
def deploy_cluster(compose_dir: str) -> str:
    """
    Deploy the Apollo Swarm using docker compose up.
    Requires YOLO Level 3 (Full YOLO).
    """
    if get_yolo_level() < 3:
        return f"Error: YOLO Level {get_yolo_level()} blocks deployment commands. Need Level 3 (Full YOLO)."
        
    try:
        # Run docker compose in detached mode
        cmd = f"cd {compose_dir} && sudo docker compose up -d"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60)
        output = result.stdout
        if result.stderr:
            output += f"\n--- stderr ---\n{result.stderr}"
        return output
    except Exception as e:
        return f"Error deploying cluster: {e}"

@mcp.tool()
def install_package(package_name: str, manager: str = "pacman") -> str:
    """
    Install a Linux package using the specified manager ('pacman' or 'apt').
    Requires YOLO Level 3 (Full YOLO).
    """
    if get_yolo_level() < 3:
        return f"Error: YOLO Level {get_yolo_level()} blocks package installations. Need Level 3 (Full YOLO)."
        
    if manager not in ["pacman", "apt"]:
        return f"Error: Unsupported package manager '{manager}'."
        
    try:
        if manager == "pacman":
            cmd = f"sudo pacman -S --noconfirm {package_name}"
        else:
            cmd = f"sudo apt install -y {package_name}"
            
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=120)
        output = result.stdout
        if result.stderr:
            output += f"\n--- stderr ---\n{result.stderr}"
        return output
    except Exception as e:
        return f"Error installing package: {e}"

@mcp.tool()
def starbuck_write_scratchpad(key: str, value: str) -> str:
    """
    Write or update a value in the cluster-wide Agentic Scratchpad.
    Use this to store transient deployment notes, like VRAM boundary calculations,
    so they are accessible to the entire swarm.
    Requires YOLO Level >= 1.
    """
    if get_yolo_level() < 1:
        return "Error: write_scratchpad requires YOLO Level >= 1."
        
    try:
        api_url = os.environ.get("MESSAGE_BUS_API", "http://127.0.0.1:8000").rstrip("/")
        data = json.dumps({"key": key, "value": value}).encode("utf-8")
        req = urllib.request.Request(
            f"{api_url}/scratchpad",
            data=data,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            if res_data.get("status") == "ok":
                 return f"Successfully wrote to scratchpad: {key}"
            return f"Failed to write to scratchpad: {res_data}"
    except Exception as e:
        return f"Error writing to scratchpad: {e}"

@mcp.tool()
def starbuck_read_scratchpad(key: str) -> str:
    """
    Read a value from the cluster-wide Agentic Scratchpad.
    Requires YOLO Level >= 1.
    """
    if get_yolo_level() < 1:
        return "Error: read_scratchpad requires YOLO Level >= 1."
        
    try:
        api_url = os.environ.get("MESSAGE_BUS_API", "http://127.0.0.1:8000").rstrip("/")
        req = urllib.request.Request(f"{api_url}/scratchpad/{key}")
        with urllib.request.urlopen(req) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            return res_data.get("value", "")
    except urllib.error.HTTPError as e:
        if e.code == 404:
             return f"Scratchpad key not found: {key}"
        return f"HTTP Error reading from scratchpad: {e.code}"
    except Exception as e:
        return f"Error reading from scratchpad: {e}"

@mcp.tool()
def starbuck_manage_service(action: str, service_name: str) -> str:
    """
    Manage a systemd service.
    Allowed actions: 'start', 'stop', 'restart', 'enable', 'disable', 'status'.
    Requires YOLO Level 3 (Full YOLO). 'status' requires YOLO Level >= 0.
    """
    allowed_actions = ["start", "stop", "restart", "enable", "disable", "status"]
    if action not in allowed_actions:
        return f"Error: Action must be one of {allowed_actions}."
        
    yolo_level = get_yolo_level()
    if action != "status" and yolo_level < 3:
         return "Error: Modifying services requires YOLO Level 3."
         
    try:
        cmd = f"sudo systemctl {action} {service_name}"
        if action == "status":
             cmd = f"systemctl status {service_name} --no-pager"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60)
        output = result.stdout
        if result.stderr:
             output += f"\n--- stderr ---\n{result.stderr}"
        return output
    except Exception as e:
        return f"Error managing service: {e}"

@mcp.tool()
def starbuck_read_journal(service_name: str, lines: int = 50) -> str:
    """
    Read the systemd journal for a specific service.
    Requires YOLO Level >= 1.
    """
    if get_yolo_level() < 1:
         return "Error: Reading journal requires YOLO Level >= 1."
         
    try:
        cmd = f"journalctl -u {service_name} -n {lines} --no-pager"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60)
        output = result.stdout
        if result.stderr:
             output += f"\n--- stderr ---\n{result.stderr}"
        return output
    except Exception as e:
        return f"Error reading journal: {e}"

@mcp.tool()
def starbuck_execute_fix(command: str) -> str:
    """
    Executes a raw bash command to resolve dependency conflicts.
    This tool is gated at YOLO Level 3. Use strictly for package manager repair operations.
    """
    if get_yolo_level() < 3:
        return f"Error: YOLO Level {get_yolo_level()} blocks raw execution commands. Need Level 3 (Full YOLO)."

    try:
        result = subprocess.run(command, shell=True, text=True, capture_output=True, timeout=30)
        return f"Exit Code: {result.returncode}\n\nSTDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}"
    except Exception as e:
        return f"Execution Failed: {str(e)}"

if __name__ == "__main__":
    # Start the FastMCP stdio server
    mcp.run(transport='stdio')
