#!/bin/bash
# Auto-updater for the Gemini CLI Nightly branch
echo "[*] Updating Gemini CLI to the latest nightly build..."
sudo npm install -g @google/gemini-cli@nightly

echo "[*] Verifying installation..."
gemini --version

echo "[+] Update complete. The silent-hang timeouts and auto-retries are now active."