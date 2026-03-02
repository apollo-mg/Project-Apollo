#!/bin/bash
echo "--- 🚀 INITIATING APOLLO ROCM 7.2 UPGRADE ---"

# 1. Download the new ROCm 7.2 installer
echo "Downloading ROCm 7.2 packages..."
wget https://repo.radeon.com/amdgpu-install/7.2/ubuntu/jammy/amdgpu-install_7.2.70200-1_all.deb

# 2. Stop all AI processes to free the GPU
echo "Stopping Apollo services..."
systemctl --user stop mbsync.timer
pkill -f background_chronicler.py
pkill -f discord_bridge.py
sudo systemctl stop ollama

# 3. Install the new repository keys
echo "Installing new repository configuration..."
sudo apt-get install -y ./amdgpu-install_7.2.70200-1_all.deb

# 4. Run the upgrade
echo "Running the ROCm upgrade..."
sudo apt-get update
sudo amdgpu-install --usecase=rocm,graphics --no-32 -y

echo "--- ✅ UPGRADE COMPLETE ---"
echo "You MUST reboot your system for the new RDNA 4 kernel drivers to take effect."
echo "Run: sudo reboot"
