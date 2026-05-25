import os
import time
import shutil
from zipfile import ZipFile

# Configuration: What are we saving?
# We focus on the 'Soul' files and the Vault
CRITICAL_FILES = [
    'buddy_agent.py', 
    'shop_dossier.json', 
    'active_project.md',
    'SHOP_BUDDY_ROADMAP.md',
    'buddy_persona.md',
    'llm_interface.py',
    'vram_management.py',
    'buddy_guardian.py',
    'guardian_config.json'
]
CRITICAL_DIRS = ['vault']

# Mount Point (Local Google Drive Mirror)
# Adapted for Mark's likely file structure
BACKUP_DIR = "/media/mark/TG 2TB/AI/Backups/Shop_Buddy"

def backup_files():
    if not os.path.exists(BACKUP_DIR):
        try:
            os.makedirs(BACKUP_DIR, exist_ok=True)
        except:
            print(f"Error: Could not access backup mount at {BACKUP_DIR}")
            return

    current_time = time.strftime('%Y%m%d_%H%M%S')
    backup_name = f'shop_snapshot_{current_time}.zip'
    temp_zip = os.path.join("/tmp", backup_name)

    try:
        with ZipFile(temp_zip, 'w') as zip_file:
            # Individual files
            for f in CRITICAL_FILES:
                if os.path.exists(f):
                    zip_file.write(f)
            
            # Vault directory
            for directory in CRITICAL_DIRS:
                if os.path.exists(directory):
                    for root, _, files in os.walk(directory):
                        for file in files:
                            path = os.path.join(root, file)
                            zip_file.write(path, os.path.relpath(path, "."))
        
        # Move to cloud mount
        shutil.move(temp_zip, os.path.join(BACKUP_DIR, backup_name))
        print(f"Snapshot Successful: {backup_name}")
        
        # Simple Rotation: Keep last 10 snapshots
        all_snapshots = sorted([f for f in os.listdir(BACKUP_DIR) if f.startswith('shop_snapshot')])
        if len(all_snapshots) > 10:
            for old_f in all_snapshots[:-10]:
                os.remove(os.path.join(BACKUP_DIR, old_f))
                
    except Exception as e:
        print(f"Backup failed: {str(e)}")

if __name__ == '__main__':
    backup_files()
