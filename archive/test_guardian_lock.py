import local_agent
import os
import json
import time

def test_lockdown():
    print("--- TESTING GUARDIAN LOCKDOWN MECHANISM ---")
    
    # 1. Ensure clean state
    if os.path.exists("guardian_lock.json"):
        os.remove("guardian_lock.json")
    
    assert not local_agent.check_guardian_lock(), "System should be UNLOCKED initially."
    
    # 2. Trigger Lockdown
    print("Triggering Lockdown...")
    # This will attempt to POST to Klipper, which might fail if not running, but that's expected.
    # We care about the lock file.
    try:
        local_agent.trigger_lockdown("TEST P0 EVENT")
    except Exception as e:
        print(f"(Expected error if Klipper is offline: {e})")
        
    # 3. Verify Lock
    assert os.path.exists("guardian_lock.json"), "Lock file MUST exist after trigger."
    
    with open("guardian_lock.json", 'r') as f:
        data = json.load(f)
        print(f"Lock Data: {data}")
        assert data['locked'] == True
        assert data['reason'] == "TEST P0 EVENT"
        
    assert local_agent.check_guardian_lock(), "System should be LOCKED now."
    
    print("--- LOCKDOWN TEST PASSED ---")
    
    # 4. Cleanup
    os.remove("guardian_lock.json")
    print("Cleanup complete.")

if __name__ == "__main__":
    test_lockdown()
