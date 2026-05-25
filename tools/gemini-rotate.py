#!/usr/bin/env python3
import os
import json
import shutil
import sys

# Define Paths
GEMINI_DIR = os.path.expanduser("~/.gemini")
STATE_FILE = os.path.join(GEMINI_DIR, "rotation_state.json")
CREDS_FILE = os.path.join(GEMINI_DIR, "oauth_creds.json")
API_KEY_FILE = os.path.join(GEMINI_DIR, "api_key.txt")
VAULT_DIR = os.path.join(GEMINI_DIR, "vault")

def init_state():
    """Initialize or upgrade the rotation state file."""
    if not os.path.exists(STATE_FILE):
        # Check if the old accounts file exists to migrate
        old_file = os.path.join(GEMINI_DIR, "google_accounts.json")
        if os.path.exists(old_file):
            with open(old_file, "r") as f:
                old_data = json.load(f)
            state = {
                "mode": "api_key", # Start with API key by default
                "api_keys": {
                    "active": "",
                    "old": []
                },
                "oauth": {
                    "active": old_data.get("active", ""),
                    "old": old_data.get("old", [])
                }
            }
            print("[*] Migrated old google_accounts.json to new rotation_state.json")
        else:
            state = {
                "mode": "api_key",
                "api_keys": {"active": "", "old": []},
                "oauth": {"active": "", "old": []}
            }
        
        os.makedirs(GEMINI_DIR, exist_ok=True)
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)
        return state
    else:
        with open(STATE_FILE, "r") as f:
            return json.load(f)

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

def set_active_api_key(key):
    """Write the API key to a file that the environment can source or CLI can read."""
    # We write it to a text file. The user will need to export GEMINI_API_KEY=$(cat ~/.gemini/api_key.txt)
    # Or if the CLI natively supports reading from a config, we'd write it there.
    # For now, we write it to the environment config.
    with open(API_KEY_FILE, "w") as f:
        f.write(key.strip())
    
    # Also update the shell profile wrapper if necessary, but writing to the file is safest.
    print(f"[*] Activated API Key. (Ensure your shell exports GEMINI_API_KEY from {API_KEY_FILE})")

def clear_api_key():
    if os.path.exists(API_KEY_FILE):
        os.remove(API_KEY_FILE)
    print("[*] Cleared API Key (Falling back to OAuth).")

def rotate_api_keys(state):
    active = state["api_keys"].get("active")
    old = state["api_keys"].get("old", [])

    if not active and not old:
        print("[!] No API keys found in pool. Switching to OAuth mode.")
        state["mode"] = "oauth"
        return rotate_oauth(state)

    if not old:
        print("[!] Only one API key in the pool. It is probably exhausted.")
        print("[*] Switching to OAuth fallback mode.")
        state["mode"] = "oauth"
        return rotate_oauth(state)

    # Rotate
    new_active = old.pop(0)
    if active:
        old.append(active)
    
    state["api_keys"]["active"] = new_active
    state["api_keys"]["old"] = old
    
    set_active_api_key(new_active)
    print(f"[+] Rotated to next API Key in the pool.")
    return state

def rotate_oauth(state):
    # Ensure vault exists
    os.makedirs(VAULT_DIR, exist_ok=True)
    clear_api_key() # Ensure API key doesn't override OAuth

    active = state["oauth"].get("active")
    old = state["oauth"].get("old", [])

    if not active or not old:
        print("Error: Not enough OAuth accounts to rotate.")
        sys.exit(1)

    # 1. Vault the current credentials
    if os.path.exists(CREDS_FILE) and active:
        vault_path = os.path.join(VAULT_DIR, f"oauth_creds_{active}.json")
        shutil.copy2(CREDS_FILE, vault_path)
        print(f"[*] Vaulted OAuth credentials for: {active}")

    # 2. Rotate the list
    new_active = old.pop(0)
    old.append(active)
    
    state["oauth"]["active"] = new_active
    state["oauth"]["old"] = old

    # 3. Restore the next account's credentials if they exist
    next_vault_path = os.path.join(VAULT_DIR, f"oauth_creds_{new_active}.json")
    if os.path.exists(next_vault_path):
        shutil.copy2(next_vault_path, CREDS_FILE)
        print(f"[+] Restored OAuth credentials for: {new_active}")
        print("\nSUCCESS: You can now launch Gemini CLI with the new OAuth quota.")
    else:
        # If we haven't vaulted this one yet, clear the active creds so the CLI forces a clean /auth
        if os.path.exists(CREDS_FILE):
            os.remove(CREDS_FILE)
        print(f"[!] No vaulted credentials found for: {new_active}")
        print("    You will need to run '/auth' ONE TIME for this account.")
        print("    Once authenticated, it will be automatically vaulted next time you rotate.")
    
    return state

def main():
    state = init_state()

    # If the user explicitly passes a flag, we can force a mode
    if len(sys.argv) > 1:
        if sys.argv[1] == "--oauth":
            state["mode"] = "oauth"
        elif sys.argv[1] == "--apikey":
            state["mode"] = "api_key"

    print(f"--- Gemini Quota Rotation (Current Mode: {state['mode'].upper()}) ---")

    if state["mode"] == "api_key":
        state = rotate_api_keys(state)
    else:
        state = rotate_oauth(state)

    save_state(state)

if __name__ == "__main__":
    main()