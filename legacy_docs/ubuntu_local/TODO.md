# PROJECT APOLLO: ACTIVE TODO LIST
**Last Updated:** March 11, 2026

## 🔴 CRITICAL / HIGH PRIORITY
- [ ] **Fix vLLM Native Import**: Resolve the \`undefined symbol: _ZN3c103hip19getCurrentHIPStreamEa\` error in the \`venv_apollo\` environment on the desktop. 
- [ ] **Vision OCR for Receipts**: Build a "Receipt Ingester" that uses the Pi 5 camera or a provided photo to update the \`price_expert.py\` with non-digital data.
- [ ] **Stabilize Resident Engine**: Ensure the \`resident_engine.sh\` script starts reliably on desktop boot and correctly allocates VRAM.

## 🟡 MEDIUM PRIORITY
- [ ] **Vision Agent Integration**: Hook \`apollo_vision.py\` into the main \`buddy_agent.py\` so the system can autonomously decide when it needs to "see" the desktop.
- [ ] **Forensic Archive Ingestion**: Run a batch processing task on \`/home/gemini/gemini/tmp/vision/\` to generate a structured JSON database of hardware.
- [ ] **Dashboard v2**: Add a "Shopping List" view to the mobile dashboard that syncs with Google Keep.

## 🟢 LOW PRIORITY / EXPLORATORY
- [ ] **AMD MCP Profiling**: Investigate the new "HPC Coding Agent" MCP tool from the ROCm blog.
- [ ] **Pi Voice Bridge**: Prototype the Pi 5 as a remote microphone endpoint for the main GPU server.

## ✅ RECENTLY COMPLETED
- [x] **Mobile Pulse Dashboard**: Live workstation stats and price audit triggers on Port 8081.
- [x] **Truth-in-Pricing Engine**: Automatic BOGO/Mega-Sale trick detection.
- [x] **Flyer Scraper**: Automated daily sync for Walmart/Kroger (46151).
- [x] **Sovereign Style Guide**: Logged permanent user preferences for procurement.
- [x] **Crash Recovery**: Fixed Pi 5 OOM and restored Whisper server on Port 8080.

### 🥧 Pi Swarm Expansion
- [ ] Order I2S Mic/Speaker for Pi Zero 2 W (AliExpress).
- [ ] Mount Pi 4 "Sentry" over workbench for Vision 2.0.
- [ ] Define Swarm communication ports (UDP 5005 for Audio, TCP 8081 for Vision).
