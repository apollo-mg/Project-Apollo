import os
import json
import psutil
import subprocess
import vram_management
import system_monitor
import task_manager
import time
import requests
from dotenv import load_dotenv
from buddy_guardian import SovereignGuardian
import llm_interface

# Load env for tokens
load_dotenv()

PENDING_PATH = "modules/approvals/pending.json"
CHRONICLER_LOG = "chronicler_background.log"
DISCORD_LOG = "discord_bridge.log"
BRIDGE_LOG = "apollo_bridge.log"
CAD_LOG = "vault/cad_training.jsonl"
EMAIL_KEYS_FILE = "vault/email_processed_keys.txt"

def get_service_status(unit_name):
    try:
        res = subprocess.run(["systemctl", "--user", "is-active", unit_name], capture_output=True, text=True)
        return res.stdout.strip().upper()
    except: return "UNKNOWN"

def get_log_tail(file_path, lines=3):
    if not os.path.exists(file_path): return ["Log not found."]
    try:
        with open(file_path, 'r') as f:
            content = f.readlines()
            return [l.strip() for l in content[-lines:]]
    except: return ["Error reading log."]

def check_port(url):
    try:
        res = requests.get(url, timeout=0.5)
        return "ONLINE" if res.status_code == 200 else "ERROR"
    except: return "OFFLINE"

def get_dashboard():
    """
    The Glass Cockpit of Apollo.
    Aggregates stats, health, and availability into a clean report.
    """
    # 0. LLM Model Status
    loaded_models = llm_interface.get_loaded_models()
    model_status = {
        "Engineer (DeepSeek)": "RESIDENT" if any("deepseek" in m for m in loaded_models) else "READY (On-Demand)",
        "Architect (Qwen3)": "RESIDENT" if any("qwen3-coder:30b" in m for m in loaded_models) else "READY (On-Demand)",
        "Vision (Qwen2.5)": "RESIDENT" if any("qwen" in m for m in loaded_models) else "READY (On-Demand)",
        "Receptionist (Llama)": "RESIDENT" if any("llama" in m for m in loaded_models) else "ONLINE"
    }

    # 1. Hardware Stats
    gpu = vram_management.get_gpu_stats()
    sys = system_monitor.get_system_stats()
    
    # 2. Integrity Check
    integrity = SovereignGuardian.check_system_integrity()
    
    # 3. Voice Infrastructure (New)
    whisper_status = check_port("http://127.0.0.1:8080/")
    bridge_status = check_port("http://127.0.0.1:5000/health")
    
    # Check Pi 5 via ping
    pi_ip = "10.0.0.118"
    pi_ping = os.system(f"ping -c 1 -W 1 {pi_ip} > /dev/null 2>&1")
    pi_status = "REACHABLE" if pi_ping == 0 else "OFFLINE"

    # 4. Background Services & Tasks
    mbsync_status = get_service_status("mbsync.timer")
    
    # Check background processes
    chronicler_active = "OFFLINE"
    discord_active = "OFFLINE"
    bot_name = ""
    for p in psutil.process_iter(['cmdline']):
        try:
            cmdline = ' '.join(p.info['cmdline']) if p.info['cmdline'] else ""
            if 'background_chronicler.py' in cmdline:
                chronicler_active = "ONLINE"
            if 'discord_bridge.py' in cmdline:
                discord_active = "ONLINE"
                if os.path.exists(DISCORD_LOG):
                    with open(DISCORD_LOG, 'r') as f:
                        lines = f.readlines()
                        for line in reversed(lines):
                            if "Logged in as" in line:
                                bot_name = line.split("as")[-1].split("(ID")[0].strip()
                                break
        except (psutil.NoSuchProcess, psutil.AccessDenied): continue

    # 5. Discord Mapping
    channels = {
        "General": os.getenv("CHANNEL_GENERAL", "N/A"),
        "Engineer": os.getenv("CHANNEL_ENGINEER", "N/A"),
        "Monitoring": os.getenv("CHANNEL_MONITORING", "N/A"),
        "Vision": os.getenv("CHANNEL_VISION", "N/A"),
        "Librarian": os.getenv("CHANNEL_LIBRARIAN", "N/A"),
        "Planner": os.getenv("CHANNEL_PLANNER", "N/A"),
        "Shopping": os.getenv("CHANNEL_SHOPPING", "N/A")
    }

    # 6. Ingestion Progress
    indexed_emails = 0
    if os.path.exists(EMAIL_KEYS_FILE):
        with open(EMAIL_KEYS_FILE, 'r') as f:
            indexed_emails = sum(1 for _ in f)

    cad_entries = 0
    if os.path.exists(CAD_LOG):
        with open(CAD_LOG, 'r') as f:
            cad_entries = sum(1 for _ in f)

    # 7. Synthesis
    report = [
        "--- 🛰️  APOLLO GLASS COCKPIT ---",
        f"INTEGRITY: {integrity} | TIME: {time.strftime('%H:%M:%S')}",
        "",
        "🧠 LLM MODEL REGISTRY:",
        f"  - Engineer (DeepSeek): {model_status['Engineer (DeepSeek)']}",
        f"  - Architect (Qwen3): {model_status['Architect (Qwen3)']}",
        f"  - Vision (Qwen2.5): {model_status['Vision (Qwen2.5)']}",
        f"  - Receptionist (Llama): {model_status['Receptionist (Llama)']}",
        "",
        "🎙️ VOICE INFRASTRUCTURE:",
        f"  - Whisper Server (8080): {whisper_status}",
        f"  - Apollo Bridge (5000): {bridge_status}",
        f"  - Zoey Satellite (Pi 5): {pi_status} ({pi_ip})",
        "",
        "💻 HARDWARE STATUS:",
        f"  - CPU: {sys['cpu_percent']}% (Temp: {sys['cpu_temp']}°C)",
        f"  - RAM: {sys['ram']['percent']}% ({sys['ram']['used_gb']}G/{sys['ram']['total_gb']}G)",
        f"  - GPU: {gpu['vram_used_mb']:.0f}MB / {gpu['vram_total_mb']:.0f}MB ({gpu['vram_percent']:.1f}%)",
        f"  - GPU Temps: Core {gpu['temperature_edge']}°C | VRAM {gpu['temperature_mem']}°C",
        f"  - GPU Fan: {gpu['fan_speed_pct']}% | Power: {gpu['power_draw_w']}W",
        "",
        "🔄 BACKGROUND FLOWS:",
        f"  - Mail Sync (mbsync): {mbsync_status}",
        f"  - Chronicler (Ingest): {chronicler_active} ({indexed_emails} indexed)",
        f"  - Discord Bridge: {discord_active} ({bot_name if bot_name else ('TOKEN_OK' if os.getenv('DISCORD_TOKEN') else 'NO_TOKEN')})",
        f"  - DesignMind Training: {cad_entries} samples logged",
        "",
        "📜 RECENT LOG TRACE (Zoey Bridge):"
    ]
    
    for line in get_log_tail(BRIDGE_LOG, lines=4):
        report.append(f"    > {line}")

    # 8. Tasks & Approvals
    tasks = task_manager.load_tasks()
    open_tasks = [t for t in tasks if t["status"] == "open"]
    
    pending_approvals = []
    if os.path.exists(PENDING_PATH):
        try:
            with open(PENDING_PATH, 'r') as f:
                queue = json.load(f)
                pending_approvals = [v for k, v in queue.items() if v["status"] == "pending"]
        except: pass

    report.append("")
    report.append(f"📋 TASKS: {len(open_tasks)} open.")
    report.append(f"⚠️  APPROVALS: {len(pending_approvals)} pending.")
    
    if pending_approvals:
        for app in pending_approvals[:3]:
            report.append(f"    - [{app['action']}] {app['params'][:50]}...")
            
    return "\n".join(report)

if __name__ == "__main__":
    print(get_dashboard())
