#!/usr/bin/env python3
import hashlib
import json
import os
from buddy_guardian import CORE_FILES, MANIFEST_PATH

def generate_manifest():
    print(f"--- [SEALING SYSTEM: Generating {MANIFEST_PATH}] ---")
    manifest = {}
    for file in CORE_FILES:
        if not os.path.exists(file):
            print(f"⚠️  WARNING: Missing core file: {file}")
            continue
        
        with open(file, "rb") as f:
            file_hash = hashlib.sha256(f.read()).hexdigest()
            manifest[file] = file_hash
            print(f"✅ Hashed: {file} ({file_hash[:8]}...)")
            
    with open(MANIFEST_PATH, 'w') as f:
        json.dump(manifest, f, indent=4)
    
    print("\n[OK] SYSTEM SEALED. Apollo will now monitor for any modifications to these files.")

if __name__ == "__main__":
    confirm = input("Are you sure you want to update the system manifest? (y/n): ").strip().lower()
    if confirm == 'y':
        generate_manifest()
    else:
        print("Operation cancelled.")
