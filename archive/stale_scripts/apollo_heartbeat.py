import os
import json
import time
import asyncio
import psutil
import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Ensure data directory exists
os.makedirs("data", exist_ok=True)
QUEUE_FILE = "data/heartbeat_queue.json"
DROP_DIR = "vault/drop"
os.makedirs(DROP_DIR, exist_ok=True)

def inject_task(source, urgency, description, context=None):
    """Safely appends a new task to the Heartbeat Queue."""
    task = {
        "id": f"HB-{int(time.time())}",
        "timestamp": datetime.datetime.now().isoformat(),
        "source": source,
        "urgency": urgency,
        "description": description,
        "context": context or {},
        "status": "pending"
    }
    
    # Simple file lock mechanism via read/write
    try:
        tasks = []
        if os.path.exists(QUEUE_FILE):
            with open(QUEUE_FILE, 'r', encoding='utf-8') as f:
                tasks = json.load(f)
        
        # Rate limit check (e.g., don't spam thermal alerts)
        if source == "thermal":
            recent = [t for t in tasks if t["source"] == "thermal" and t["status"] == "pending"]
            if recent:
                return # Skip, already have a pending thermal alert
                
        tasks.append(task)
        
        with open(QUEUE_FILE, 'w', encoding='utf-8') as f:
            json.dump(tasks, f, indent=2)
            
        print(f"[HEARTBEAT] 💓 Injected {urgency.upper()} task from {source}.")
    except Exception as e:
        print(f"[HEARTBEAT] ❌ Failed to inject task: {e}")

class DropFolderHandler(FileSystemEventHandler):
    def on_created(self, event):
        if not event.is_directory:
            inject_task(
                source="file_system",
                urgency="normal",
                description=f"New file detected in drop folder: {os.path.basename(event.src_path)}",
                context={"file_path": event.src_path}
            )

async def monitor_thermals():
    """Polls CPU thermals every 10 seconds."""
    while True:
        try:
            # Requires sensors to be configured on Linux
            if hasattr(psutil, "sensors_temperatures"):
                temps = psutil.sensors_temperatures()
                if 'k10temp' in temps: # AMD Ryzen default sensor
                    for entry in temps['k10temp']:
                        if entry.current > 85.0: # High threshold
                            inject_task(
                                source="thermal",
                                urgency="high",
                                description=f"CPU Temperature spike detected: {entry.current}°C",
                                context={"temp": entry.current, "sensor": entry.label}
                            )
        except Exception as e:
            pass
        await asyncio.sleep(10)

async def monitor_emails():
    """Hourly email scan routine."""
    while True:
        # Wait 1 hour (3600 seconds) - setting to 60 seconds for initial testing
        # TODO: Change back to 3600 after verifying the loop works
        await asyncio.sleep(3600) 
        
        print("[HEARTBEAT] 📧 Initiating hourly email sync and triage...")
        # We don't do the heavy LLM processing here to keep the daemon lightweight.
        # Instead, we inject a task for Zoey to do it when she is idle.
        inject_task(
            source="email_scheduler",
            urgency="normal",
            description="Hourly email triage required. Run sync_mail() and analyze recent urgent/personal messages.",
            context={"time_since_last_check": "1 hour"}
        )

async def main():
    print(f"🚀 Apollo Heartbeat Daemon Starting...")
    print(f"📁 Monitoring Drop Folder: {DROP_DIR}")
    
    # 1. Start Watchdog Observer (File System)
    observer = Observer()
    observer.schedule(DropFolderHandler(), path=DROP_DIR, recursive=False)
    observer.start()

    # 2. Start Async Pollers (Thermals & Scheduled Tasks)
    tasks = [
        asyncio.create_task(monitor_thermals()),
        asyncio.create_task(monitor_emails()),
        asyncio.create_task(monitor_github_turboquant())
    ]
    
    try:
        await asyncio.gather(*tasks)
    except KeyboardInterrupt:
        print("\n🛑 Heartbeat Daemon Terminating...")
        observer.stop()
    
    observer.join()

if __name__ == "__main__":
    asyncio.run(main())                       source="github_monitor",
                        urgency="high",
                        description="🚨 BREAKING: TurboQuant KV Cache PR has been merged into llama.cpp master branch! Recommend immediate pull and recompile to unlock massive context windows.",
                        context={"items": [item["html_url"] for item in data.get("items", [])[:3]]}
                    )
                    # Sleep for a week so we don't spam once it's merged
                    await asyncio.sleep(604800)
                    continue
        except Exception as e:
            pass # Fail silently, it's just a background check
            
        # Check again in 24 hours (86400 seconds)
        await asyncio.sleep(86400)

async def main():
    print(f"🚀 Apollo Heartbeat Daemon Starting...")
    print(f"📁 Monitoring Drop Folder: {DROP_DIR}")
    
    # 1. Start Watchdog Observer (File System)
    observer = Observer()
    observer.schedule(DropFolderHandler(), path=DROP_DIR, recursive=False)
    observer.start()

    # 2. Start Async Pollers (Thermals & Scheduled Tasks)
    tasks = [
        asyncio.create_task(monitor_thermals()),
        asyncio.create_task(monitor_emails())
    ]
    
    try:
        await asyncio.gather(*tasks)
    except KeyboardInterrupt:
        print("\n🛑 Heartbeat Daemon Terminating...")
        observer.stop()
    
    observer.join()

if __name__ == "__main__":
    asyncio.run(main())