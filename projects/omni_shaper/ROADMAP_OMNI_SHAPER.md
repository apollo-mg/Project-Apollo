# 🌀 PROJECT OMNI-SHAPER: THE VIBRATION SOVEREIGNTY ROADMAP
**Status:** Inception / Research Phase
**Goal:** Transform 13x 16-bit SlimeVR sensors into a "Modal Mesh" for real-time active vibration mitigation.

---

## 🔨 Phase 0: The "Tap Test" MVP (Hardware Agnostic)
*   **Objective:** Validate the core physics of the Triangulation Dance using existing Wi-Fi ESP8266/BMI270 trackers on a generic surface.
*   **Milestones:**
    *   [ ] **The Setup**: Tape the Main Tracker to the center of a desk and the Extension Tracker to the edge.
    *   [ ] **OSC Listener**: Write a standalone Python script (`tap_listener.py`) to catch SlimeVR UDP packets over Wi-Fi.
    *   [ ] **The "Chirp"**: Physically tap the desk with a screwdriver handle to create a mechanical shockwave.
    *   [ ] **Phase Shift Validation**: Measure the time delay (ToA) between the shockwave hitting the Main Tracker vs. the Extension Tracker to prove spatial triangulation works despite Wi-Fi jitter.

## 🛰️ Phase I: The Listener (Hardware Interfacing)
*   **Objective:** Establish a high-fidelity, low-latency data pipe from SlimeVR dongles to the Sovereign Engine.
*   **Milestones:**
    *   [ ] **OSC Intercept Script**: Build a lightweight Python listener (`omni_listener.py`) to capture raw 16-bit IMU packets via UDP.
    *   [ ] **Data Buffer & Logging**: Implement a high-speed ring buffer to store timestamped acceleration and quaternion data.
    *   [ ] **Noise Floor Analysis**: Profile the BMI270/ICM-42688 sensors against the standard ADXL345 to verify the "16-bit advantage."

## 💃 Phase II: The Triangulation Dance (Spatial Awareness)
*   **Objective:** Solve the "Hard Part"—mapping sensor XYZ coordinates relative to the nozzle without manual measurement.
*   **Milestones:**
    *   [ ] **The Calibration Beacon**: Write a Klipper macro to emit a 10Hz physical "chirp" at known X/Y/Z coordinates.
    *   [ ] **ToA/Phase-Shift Algorithm**: Implement Multilateration math to calculate the distance between the beacon (nozzle) and each sensor node.
    *   [ ] **Auto-Topology Mapping**: Generate a 3D visual "map" of where all 13 sensors are sitting on the frame/desk.

## 🧮 Phase III: The Master Matrix (System Modeling)
*   **Objective:** Build a "Digital Twin" of the machine's mechanical physics.
*   **Milestones:**
    *   [ ] **MIMO State-Space Core**: Use the RDNA 4 GPU (gfx1201) to solve the $(M, C, K)$ matrix representing Mass, Damping, and Stiffness.
    *   [ ] **Broadband Frequency Sweep**: Run a 1Hz to 500Hz "chirp" to identify the frame’s natural frequencies and "Harmonic Traps."
    *   [ ] **The Topographical Map**: Visualize the "Energy Flow" of a move across the entire machine structure.

## ⚡ Phase IV: The Counter-Strike (Active Mitigation)
*   **Objective:** Implement Predictive Feedforward and Active Feedback loops.
*   **Milestones:**
    *   [ ] **Look-Ahead Queue Intercept**: Build a bridge to the Klipper motion planner to see upcoming moves.
    *   [ ] **Predictive Feedforward**: Pre-calculate the "Counter-Pulse" for 15,000 mm/s² accelerations.
    *   [ ] **Active Feedback (AVC)**: Prototype "destructive interference" using tactile transducers (bass shakers) to cancel resonant hums.

## 📦 Phase V: The Vault (IP & Productization)
*   **Objective:** Secure the IP and package the "Widowmaker Suite" for the prosumer market.
*   **Milestones:**
    *   [ ] **Provisional Patent (PPA)**: File the "Triangulation Dance" method with the USPTO (~$75 Micro-Entity fee).
    *   [ ] **The "One-Shot" MVP**: Bundle the software into a user-friendly "SaaS for Hardware" dashboard.
    *   [ ] **Supply Chain Optimization**: Direct-source "Butterfly" spec sensors for a professional-grade kit under $200.

---
*The machine no longer guesses. It knows exactly how it flinches.*
