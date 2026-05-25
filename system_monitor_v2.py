import psutil
import os
import torch
import json
from datetime import datetime

def get_cpu_usage(interval=0.1):
    return psutil.cpu_percent(interval=interval)

def get_ram_usage():
    mem = psutil.virtual_memory()
    return {
        "total_gb": round(mem.total / (1024**3), 2),
        "available_gb": round(mem.available / (1024**3), 2),
        "percent": mem.percent,
        "used_gb": round(mem.used / (1024**3), 2)
    }

def get_cuda_usage():
    """
    Actively polls torch.cuda to get the physical reality of the GPU.
    """
    if not torch.cuda.is_available():
        return {"status": "no_cuda_detected"}
    
    try:
        # Get memory stats
        mem_info = torch.cuda.mem_get_info()
        
        # mem_info returns (free_bytes, total_bytes, used_bytes)
        # We use a more robust unpacking method.
        try:
            free_bytes, total_bytes, used_bytes = mem_info
        except ValueError:
            # If it doesn't return 3, try to infer
            if len(mem_info) == 2:
                free_bytes, total_bytes = mem_info
                used_bytes = total_bytes - free_bytes
            else:
                raise ValueError(f"Unexpected mem_info length: {len(mem_info)}")
        
        return {
            "status": "cuda_active",
            "total_gb": round(total_bytes / (1024**3), 2),
            "used_gb": round(used_bytes / (1024**3), 2),
            "free_gb": round(free_bytes / (1024**3), 2),
            "percent": round((used_bytes / total_bytes) * 100, 2)
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}

def get_system_stats():
    stats = {
        "timestamp": datetime.now().isoformat(),
        "cpu_percent": get_cpu_usage(),
        "ram": get_ram_usage(),
        "cuda": get_cuda_usage()
    }
    return stats

if __name__ == "__main__":
    print(json.dumps(get_system_stats(), indent=2))
