import time
import os
import subprocess
import psutil
import sys

# Ensure we can import vram_management
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import vram_management

# Configuration
VRAM_CRITICAL_FREE_MB = 400       # Restart if free VRAM drops below 400MB
CHECK_INTERVAL_SEC = 300          # Check every 5 minutes
PAUSE_FILE = "/mnt/TG_2TB/Projects/Apollo/daydream_pause.lock"
LLAMA_START_SCRIPT = "/mnt/TG_2TB/Projects/Apollo/start_rotorquant_no_vision.sh"
LOG_FILE = "/mnt/TG_2TB/Projects/Apollo/data/watchdog.log"

def log(msg):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    formatted_msg = f"[{timestamp}] {msg}"
    print(formatted_msg, flush=True)
    try:
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        with open(LOG_FILE, "a") as f:
            f.write(formatted_msg + "\n")
    except Exception as e:
        print(f"Failed to write to log: {e}")

def get_llama_server_pid():
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if 'llama-server' in proc.info['name'] or (proc.info['cmdline'] and 'llama-server' in proc.info['cmdline'][0]):
                return proc.info['pid']
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    return None

def restart_llama_server():
    log("🚨 CRITICAL VRAM REACHED. Initiating server restart sequence...")
    
    # 1. Pause Daydream Daemon
    log("⏸️ Pausing Daydream Daemon (Creating lock file)...")
    with open(PAUSE_FILE, "w") as f:
        f.write("Paused by VRAM Watchdog")
    
    # Give Daydream a moment to finish its current thought if it's in the middle of one
    # Actually, Daydream checks the lock BEFORE starting a thought. 
    # If it's already thinking, it will finish, then pause before the next one.
    log("Waiting 30 seconds for any active thoughts to finish...")
    time.sleep(30)
    
    # 2. Kill llama-server
    pid = get_llama_server_pid()
    if pid:
        log(f"💀 Killing llama-server (PID: {pid})...")
        try:
            p = psutil.Process(pid)
            p.terminate()
            p.wait(timeout=10)
        except psutil.NoSuchProcess:
            log("llama-server process not found. Continuing with restart...")
        except psutil.TimeoutExpired:
            log("Force killing llama-server...")
            p.kill()
            p.wait()
        except Exception as e:
            log(f"Error killing llama-server: {e}")
    else:
        log("llama-server process not found. Continuing with restart...")

    # 3. Wait for VRAM to flush
    log("🧹 Waiting for VRAM to flush...")
    # Using vram_management's wait_for_vram_release (wait for at least 10GB free to ensure complete flush)
    vram_management.wait_for_vram_release(10000, timeout_sec=15)
    
    # 4. Start llama-server
    log(f"🚀 Restarting llama-server via {LLAMA_START_SCRIPT}...")
    try:
        # Start in a new session so it detaches from the watchdog
        subprocess.Popen(["bash", LLAMA_START_SCRIPT], start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        log("Waiting for server to spin up (15 seconds)...")
        time.sleep(15)
    except Exception as e:
        log(f"❌ Failed to start llama-server: {e}")

    # 5. Resume Daydream Daemon
    log("▶️ Resuming Daydream Daemon (Removing lock file)...")
    try:
        if os.path.exists(PAUSE_FILE):
            os.remove(PAUSE_FILE)
    except Exception as e:
        log(f"Failed to remove pause lock: {e}")
        
    log("✅ Restart sequence complete.")

def main():
    log("🐕 VRAM Watchdog Started.")
    while True:
        try:
            stats = vram_management.get_gpu_stats()
            vram_used = stats.get("vram_used_mb", 0)
            vram_total = stats.get("vram_total_mb", 16384)
            
            if vram_used > 0:
                vram_free = vram_total - vram_used
                if vram_free < VRAM_CRITICAL_FREE_MB:
                    log(f"Warning: Free VRAM is {vram_free:.0f}MB (Below {VRAM_CRITICAL_FREE_MB}MB).")
                    restart_llama_server()
                else:
                    # Optional: uncomment to see regular status
                    # log(f"VRAM Check: {vram_free:.0f}MB free.")
                    pass
        except Exception as e:
            log(f"Watchdog error: {e}")
            
        time.sleep(CHECK_INTERVAL_SEC)

if __name__ == "__main__":
    main()
