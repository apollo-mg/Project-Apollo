import json
import os
import time

TASKS_FILE = "shop_tasks.json"

def load_tasks():
    if os.path.exists(TASKS_FILE):
        try:
            with open(TASKS_FILE, 'r') as f:
                return json.load(f)
        except: pass
    return []

def save_tasks(tasks):
    with open(TASKS_FILE, 'w') as f:
        json.dump(tasks, f, indent=4)

def add_task(description, priority="P1"):
    """
    Adds a new task.
    Priority: P0 (Critical), P1 (Normal), P2 (Low)
    """
    tasks = load_tasks()
    new_id = 1
    if tasks:
        new_id = max(t.get("id", 0) for t in tasks) + 1
    
    task = {
        "id": new_id,
        "description": description,
        "priority": priority.upper(),
        "status": "open",
        "created_at": time.time()
    }
    tasks.append(task)
    save_tasks(tasks)
    return f"Task #{new_id} added: {description} ({priority})"

def list_tasks(status="open"):
    """
    Lists tasks filtered by status (open/done).
    Sorted by Priority (P0 > P1 > P2).
    """
    tasks = load_tasks()
    filtered = [t for t in tasks if t["status"] == status]
    if not filtered:
        return f"No {status} tasks found."
    
    # Sort by priority (P0 < P1 < P2)
    priority_map = {"P0": 0, "P1": 1, "P2": 2}
    filtered.sort(key=lambda x: priority_map.get(x["priority"], 3))
    
    output = [f"--- {status.upper()} TASKS ---"]
    for t in filtered:
        output.append(f"[#{t['id']}] {t['priority']}: {t['description']}")
    return "\n".join(output)

def complete_task(task_id):
    """
    Marks a task as done.
    """
    tasks = load_tasks()
    for t in tasks:
        if t["id"] == int(task_id):
            t["status"] = "done"
            t["completed_at"] = time.time()
            save_tasks(tasks)
            return f"Task #{task_id} marked as done."
    return f"Task #{task_id} not found."

if __name__ == "__main__":
    # Test
    print(add_task("Test task", "P1"))
    print(list_tasks())
    print(complete_task(1))
    print(list_tasks())
