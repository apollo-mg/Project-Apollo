import time
import requests

API_URL = "http://localhost:8000/tasks/publish"

print("🔥 CHAOS MONKEY: Flooding the Sovereign Message Bus with 10 identical tasks...")

for i in range(1, 11):
    payload = {
        "task_name": f"chaos_task_{i}",
        "requirements": {
            "target_node": "any",
            "min_context": 2048,
            "min_precision": 4.0,
            "requires_internet": False
        },
        "payload": f"This is Chaos Task #{i}. Please process immediately."
    }
    
    response = requests.post(API_URL, json=payload)
    if response.status_code == 200:
        print(f"[+] Successfully queued {payload['task_name']} -> Task ID: {response.json()['task_id']}")
    else:
        print(f"[-] Failed to queue {payload['task_name']}: {response.text}")

print("\n✅ Zone flooded. Ready for concurrent wake-up!")