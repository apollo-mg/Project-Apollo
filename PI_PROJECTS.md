# 🥧 PROJECT PI: The Sovereign Nervous System
**Hardware:** Raspberry Pi 5 (8GB)
**Current Role:** Network Audio Listener (STT/TTS Satellite)

## 🛠️ Pi Todo List (Infrastructure & Networking)

### 🌐 Networking & Privacy
- [ ] **Pi-hole / AdGuard Home**: Implement network-wide DNS sinkhole to block corporate telemetry and ads at the source.
- [ ] **WireGuard VPN**: Secure encrypted tunnel for remote access to Apollo's APIs (Ollama/vLLM) without exposing ports.
- [ ] **Tailscale Mesh**: Establish the "Shadow Mind Swarm" Virtual LAN to connect legacy RX 580 nodes to the main RX 9070 XT rig.
- [ ] **Nginx Proxy Manager**: Map local services (e.g., `apollo.local`, `klipper.local`) to friendly hostnames with SSL.

### 🧠 Apollo Physical Extensions
- [ ] **Status HUD**: Attach 5-7" HDMI touch screen for real-time "VRAM Tetris" and Ingestion monitoring.
- [ ] **Vision Satellite**: Connect Pi Camera/USB Webcam for remote "Physical Eye" stream to Qwen3-VL.
- [ ] **Mosquitto MQTT Broker**: Setup the lightweight pub/sub "Nervous System" for hardware sensor telemetry.
- [ ] **Shop Bridge (Klipper)**: Integrate 3D printer control and GPIO-based workbench automation (fans/lights).

## 📋 Active Implementation Notes
- **Audio Feedback Loop:** Currently using a 15-second 'Self-Deafening' cooldown to prevent echo.
- **Power:** Pi 5 requires a high-quality 5V/5A supply for stable PCIe/USB usage.
