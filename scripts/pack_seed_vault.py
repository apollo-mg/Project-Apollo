import os
import tarfile
import json
from datetime import datetime

VAULT_DIR = "vault"
OUTPUT_FILE = "apollo_seed_vault_v1.tar.gz"
MANIFEST_FILE = "seed_manifest.json"

# The specific files/folders we want to distribute to new users
# We explicitly exclude raw logs, cold/ folders, or personal data.
TARGETS = [
    "bm25_index.db",
    "chroma_db",
    "graph_memory.db"
]

def generate_manifest():
    manifest = {
        "version": "1.0",
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "description": "Apollo Sovereign Engine - Semantic System Prompting Seed Vault",
        "contents": TARGETS
    }
    with open(MANIFEST_FILE, "w") as f:
        json.dump(manifest, f, indent=4)
    print(f"[*] Generated {MANIFEST_FILE}")

def pack_vault():
    print(f"[*] Packaging Seed Vault into {OUTPUT_FILE}...")
    with tarfile.open(OUTPUT_FILE, "w:gz") as tar:
        # Add the manifest
        tar.add(MANIFEST_FILE, arcname=MANIFEST_FILE)
        
        # Add the target databases
        for target in TARGETS:
            path = os.path.join(VAULT_DIR, target)
            if os.path.exists(path):
                print(f"    -> Adding {target}")
                tar.add(path, arcname=os.path.join(VAULT_DIR, target))
            else:
                print(f"    [!] Warning: {target} not found in {VAULT_DIR}, skipping.")

    # Cleanup manifest
    if os.path.exists(MANIFEST_FILE):
        os.remove(MANIFEST_FILE)
        
    size_mb = os.path.getsize(OUTPUT_FILE) / (1024 * 1024)
    print(f"[*] Success! Seed Vault packaged: {OUTPUT_FILE} ({size_mb:.2f} MB)")

if __name__ == "__main__":
    generate_manifest()
    pack_vault()
