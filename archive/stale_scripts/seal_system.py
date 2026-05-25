import os
import json
import hashlib
from buddy_guardian import CORE_FILES, MANIFEST_PATH

def seal_system():
    print("=== Apollo System Sealer ===")
    manifest = {}
    missing = []

    for file_path in CORE_FILES:
        if not os.path.exists(file_path):
            missing.append(file_path)
            print(f"[WARNING] Missing core file: {file_path}")
            continue
        
        with open(file_path, "rb") as f:
            file_hash = hashlib.sha256(f.read()).hexdigest()
            manifest[file_path] = file_hash
            print(f"[SEALED] {os.path.basename(file_path)} -> {file_hash[:8]}...")

    try:
        with open(MANIFEST_PATH, 'w') as f:
            json.dump(manifest, f, indent=4)
        print(f"\n✅ System successfully sealed! Manifest saved to {MANIFEST_PATH}")
    except Exception as e:
        print(f"\n❌ Error saving manifest: {e}")

    if missing:
        print(f"\n⚠️ Note: {len(missing)} expected core files were missing and could not be sealed.")

if __name__ == "__main__":
    seal_system()