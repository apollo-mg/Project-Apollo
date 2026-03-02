import requests
import time
import sys
import subprocess
import json

COMFY_URL = "http://127.0.0.1:8189"
VRAM_THRESHOLD_MB = 14500  # Danger zone
VRAM_TOTAL_MB = 16384     # RX 9070 XT

def get_gpu_stats():
    """
    Queries rocm-smi for full GPU telemetry (VRAM, Temp, Power, Fan).
    On Windows, attempts to use native methods or provides placeholders.
    """
    if sys.platform == "win32":
        # Fallback for Windows (PLACEHOLDER until more robust method added)
        # In a real scenario, could use torch.cuda.memory_stats() or pyadl
        # For now, return placeholders to prevent crashes.
        return {
            "vram_used_mb": 0,
            "vram_total_mb": VRAM_TOTAL_MB,
            "temperature_edge": "N/A",
            "power_draw_w": "N/A",
            "fan_speed_pct": "N/A"
        }

    try:
        res_mem = subprocess.run(["rocm-smi", "--showmeminfo", "vram", "--json"], capture_output=True, text=True)
        mem_data = json.loads(res_mem.stdout)
        
        res_all = subprocess.run(["rocm-smi", "-t", "-p", "-f", "-P", "--json"], capture_output=True, text=True)
        all_data = json.loads(res_all.stdout)
        
        card = "card0"
        # The key can vary between ROCm versions
        power = all_data[card].get("Average Graphics Package Power (W)")
        if power is None:
            power = all_data[card].get("average_socket_power (W)")
        if power is None:
            power = all_data[card].get("Current Graphics Package Power (W)")
            
        stats = {
            "vram_used_mb": int(mem_data[card]["VRAM Total Used Memory (B)"]) / (1024 * 1024),
            "vram_total_mb": int(mem_data[card]["VRAM Total Memory (B)"]) / (1024 * 1024),
            "vram_percent": (int(mem_data[card]["VRAM Total Used Memory (B)"]) / int(mem_data[card]["VRAM Total Memory (B)"])) * 100,
            "temperature_edge": all_data[card].get("Temperature (Sensor edge) (C)", "N/A"),
            "temperature_mem": all_data[card].get("Temperature (Sensor memory) (C)", "N/A"),
            "power_draw_w": power,
            "fan_speed_pct": all_data[card].get("Fan speed (%)", "N/A")
        }
        return stats
    except Exception as e:
        # Fallback for any other failure
        return {
            "vram_used_mb": 0,
            "vram_total_mb": VRAM_TOTAL_MB,
            "temperature_edge": "N/A",
            "power_draw_w": "N/A",
            "fan_speed_pct": "N/A",
            "error": str(e)
        }

def get_vram_usage():
    stats = get_gpu_stats()
    return stats.get("vram_used_mb", 0)

def wait_for_vram_release(target_free_mb, timeout_sec=30):
    """
    BLOCKING: Wait for the ROCm kernel to actually flush VRAM.
    Crucial for avoiding OOM kernel panics during model swaps.
    Increased timeout to 30s for stability.
    """
    start_time = time.time()
    while time.time() - start_time < timeout_sec:
        used = get_vram_usage()
        free = VRAM_TOTAL_MB - used
        if free >= target_free_mb:
            print(f"--- [VRAM: RELEASE VERIFIED ({free:.0f}MB Free)] ---", flush=True)
            time.sleep(3.0) # Kernel cooldown
            return True
        print(f"--- [VRAM: WAITING FOR FLUSH ({free:.0f}MB Free < {target_free_mb}MB Required)] ---", flush=True)
        time.sleep(1.0)
    print(f"--- [VRAM: TIMEOUT WAITING FOR RELEASE] ---", flush=True)
    return False

def unload_comfy_vram(unload_models=True, free_memory=True):
    try:
        print(f"Requesting ComfyUI VRAM cleanup...")
        requests.post(f"{COMFY_URL}/free", json={
            "unload_models": unload_models,
            "free_memory": free_memory
        }, timeout=5)
        return wait_for_vram_release(4000) # Wait for at least 4GB to be free
    except:
        return False

def smart_vram_guard():
    used = get_vram_usage()
    if used > VRAM_THRESHOLD_MB:
        return unload_comfy_vram()
    return True

if __name__ == "__main__":
    used = get_vram_usage()
    print(f"VRAM Used: {used:.2f} MB")
