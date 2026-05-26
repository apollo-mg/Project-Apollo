#!/bin/bash
set -e

# Create archive directory
mkdir -p /mnt/TG_2TB/Projects/Apollo/archive

# Array of whitelisted root-level files and directories (derived from APOLLO_CORE_MANIFEST.md)
# We are only sweeping the root directory to avoid breaking nested structures.
declare -A WHITELIST

# Root-level whitelisted directories
WHITELIST["engines"]=1
WHITELIST["modules"]=1
WHITELIST["scripts"]=1
WHITELIST["src"]=1
WHITELIST["deploy"]=1
WHITELIST["data"]=1
WHITELIST["vault"]=1
WHITELIST["chat_history"]=1
WHITELIST["models"]=1
WHITELIST["archive"]=1

# Root-level whitelisted files
WHITELIST["LOCAL_AGENT_CONTEXT.md"]=1
WHITELIST["profiles.json"]=1
WHITELIST["profiles.yaml"]=1
WHITELIST["dynamic_canvas.py"]=1
WHITELIST["message_bus_api.py"]=1
WHITELIST["worker_daemon.py"]=1
WHITELIST["run_turboquant_test.py"]=1
WHITELIST["sovereign_search.py"]=1
WHITELIST["bootstrap_swarm.sh"]=1
WHITELIST["CHANGELOG.md"]=1
WHITELIST["GEMINI.md"]=1
WHITELIST["README.md"]=1
WHITELIST["APOLLO_CORE_MANIFEST.md"]=1
WHITELIST["todo.md"]=1
WHITELIST["ui_state.json"]=1
WHITELIST["user_response.json"]=1

# Git and virtual environments
WHITELIST[".git"]=1
WHITELIST[".env"]=1
WHITELIST[".dockerignore"]=1
WHITELIST[".gitignore"]=1
WHITELIST[".venv"]=1
WHITELIST["venv_cachyos"]=1
WHITELIST["venv"]=1

# Legacy/Archival Heavy folders that shouldn't be moved inside archive/
WHITELIST["legacy_vault"]=1
WHITELIST["bin"]=1
WHITELIST["llama.cpp"]=1
WHITELIST["whisper.cpp"]=1

echo "Moving non-whitelisted root items to archive/..."

# Iterate through all files and directories in the root
for item in /mnt/TG_2TB/Projects/Apollo/* /mnt/TG_2TB/Projects/Apollo/.*; do
  # Extract the basename
  basename=$(basename "$item")
  
  # Skip current and parent directory pointers
  if [[ "$basename" == "." || "$basename" == ".." ]]; then
    continue
  fi

  # Check if the item is explicitly whitelisted
  if [[ -z "${WHITELIST[$basename]}" ]]; then
    echo "Archiving: $basename"
    mv "$item" /mnt/TG_2TB/Projects/Apollo/archive/ 2>/dev/null || echo "  Failed to move $basename"
  fi
done

echo "Repository sweep complete!"
