import psutil
import os

def get_cpu_usage(interval=1):
    """
    Returns the CPU usage percentage over `interval` seconds.
    """
    return psutil.cpu_percent(interval=interval)

def get_ram_usage():
    """
    Returns a dictionary with RAM usage stats.
    """
    mem = psutil.virtual_memory()
    return {
        "total_gb": round(mem.total / (1024**3), 2),
        "available_gb": round(mem.available / (1024**3), 2),
        "percent": mem.percent,
        "used_gb": round(mem.used / (1024**3), 2)
    }

def get_disk_usage(path="/"):
    """
    Returns disk usage stats for the given path.
    """
    try:
        disk = psutil.disk_usage(path)
        return {
            "total_gb": round(disk.total / (1024**3), 2),
            "free_gb": round(disk.free / (1024**3), 2),
            "percent": disk.percent
        }
    except Exception as e:
        return {"error": str(e)}

def get_cpu_temp():
    """
    Attempts to read CPU temperature using psutil.
    """
    try:
        temps = psutil.sensors_temperatures()
        if 'k10temp' in temps:
            return temps['k10temp'][0].current
        if 'coretemp' in temps:
            return temps['coretemp'][0].current
        # Fallback to any available
        for name, entries in temps.items():
            if entries:
                return entries[0].current
    except:
        pass
    return "N/A"

def get_system_stats(monitored_paths=None):
    """
    Aggregates all system stats into a single dictionary.
    If no monitored_paths are provided, it detects active partitions.
    """
    if monitored_paths is None:
        # Dynamically detect partitions
        monitored_paths = [p.mountpoint for p in psutil.disk_partitions() if p.fstype]

    stats = {
        "cpu_percent": get_cpu_usage(interval=0.1), # Fast interval for polling
        "cpu_temp": get_cpu_temp(),
        "ram": get_ram_usage(),
        "disks": {}
    }
    
    for path in monitored_paths:
        try:
            if os.path.exists(path):
                stats["disks"][path] = get_disk_usage(path)
        except:
            pass
            
    return stats

if __name__ == "__main__":
    import json
    print(json.dumps(get_system_stats(), indent=2))
