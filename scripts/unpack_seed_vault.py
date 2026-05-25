import os
import tarfile
import json
import sys

def unpack_vault(archive_path="apollo_seed_vault_v1.tar.gz"):
    if not os.path.exists(archive_path):
        print(f"[-] Error: Archive {archive_path} not found.")
        sys.exit(1)
        
    print(f"[*] Unpacking Seed Vault from {archive_path}...")
    
    with tarfile.open(archive_path, "r:gz") as tar:
        # Extract to current directory (which should contain vault/ and the manifest)
        tar.extractall(path=".")
        print("[*] Extraction complete.")
        
    if os.path.exists("seed_manifest.json"):
        with open("seed_manifest.json", "r") as f:
            manifest = json.load(f)
            print("\n=== Seed Vault Successfully Bootstrapped ===")
            print(f"Version: {manifest.get('version')}")
            print(f"Generated: {manifest.get('generated_at')}")
            print(f"Description: {manifest.get('description')}")
            print("============================================\n")
        # Cleanup manifest after reading
        os.remove("seed_manifest.json")
    else:
        print("[!] No manifest found in the archive.")
        
if __name__ == "__main__":
    archive = sys.argv[1] if len(sys.argv) > 1 else "apollo_seed_vault_v1.tar.gz"
    unpack_vault(archive)
