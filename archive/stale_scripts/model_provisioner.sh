#!/bin/bash
# model_provisioner.sh - Declarative model downloader

MANIFEST="/mnt/TG_2TB/Projects/Apollo/model_manifest.json"
MODEL_DIR="/mnt/TG_2TB/Projects/Apollo/models"

if [ ! -f "$MANIFEST" ]; then
    echo "Error: Manifest not found at $MANIFEST"
    exit 1
fi

echo "Starting model provisioning based on $MANIFEST..."

# Use python to parse JSON and iterate through models
python3 -c "
import json
import os
import subprocess

manifest_path = '$MANIFEST'
model_dir = '$MODEL_DIR'

with open(manifest_path, 'r') as f:
    data = json.load(f)

for model in data['models']:
    target_file = os.path.join(model_dir, model['filename'])
    
    if os.path.exists(target_file):
        print(f\"[SKIP] {model['filename']} already exists.\")
        continue
        
    print(f\"[FETCH] Downloading {model['name']} from {model['url']}...\")
    
    # Use curl to download the file
    try:
        cmd = [
            'curl', '-L', 
            '-o', target_file, 
            model['url']
        ]
        subprocess.run(cmd, check=True)
        print(f\"[SUCCESS] Downloaded {model['filename']}\")
    except subprocess.CalledProcessError as e:
        print(f\"[FAILURE] Failed to download {model['filename']}: {e}\")
"