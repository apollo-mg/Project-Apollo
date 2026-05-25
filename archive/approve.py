#!/usr/bin/env python3
import json
import os
import sys

PENDING_PATH = "gemini/modules/approvals/pending.json"

def approve_all():
    if not os.path.exists(PENDING_PATH):
        print("No pending approvals found.")
        return

    with open(PENDING_PATH, 'r+') as f:
        try:
            queue = json.load(f)
            if not queue:
                print("No pending approvals found.")
                return
            
            print(f"Approving {len(queue)} pending actions:")
            for q_id, data in queue.items():
                print(f"- {data['action']} (ID: {q_id[:8]})")
                data['status'] = 'approved'
            
            f.seek(0)
            json.dump(queue, f, indent=4)
            f.truncate()
            print("Done.")
        except Exception as e:
            print(f"Error: {e}")

def list_pending():
    if not os.path.exists(PENDING_PATH):
        print("No pending approvals found.")
        return

    with open(PENDING_PATH, 'r') as f:
        try:
            queue = json.load(f)
            if not queue:
                print("No pending approvals found.")
                return
            
            print("PENDING APPROVALS:")
            for q_id, data in queue.items():
                print(f"[{q_id[:8]}] {data['action']} - {data['params']}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "all":
            approve_all()
        elif sys.argv[1] == "list":
            list_pending()
        else:
            print("Usage: python3 approve.py [all|list]")
    else:
        list_pending()
