# SYSTEM DOSSIER: Ender 6 "Vz-Hybrid"
**Role:** Primary Source of Truth for Autonomous Agents
**Last Updated:** Feb 7, 2026

## 1. Visual Identity (For Vision Agents)
*   **Chassis:** Black enclosed Cube (Creality Ender 6 frame).
*   **Toolhead:** "EVA-Vz Hybrid" - Likely black CF-ASA printed parts with a silver 5mm aluminum top plate.
*   **Gantry:** Black Carbon Fiber 2020 square tube.
*   **Motors:** Silver/Black LDO motors.
*   **Bed:** 250x250mm build area (approx visual). PEI Sheet (Gold/Black).

## 2. Mechanical Limits (For Motion Agents)
*   **Kinematics:** CoreXY (Motors A/B at rear).
*   **Axis Limits (Hard):**
    *   X: 0 to 248mm
    *   Y: -2 to 320mm (Effective print area stops ~300mm).
    *   Z: 0 to 300mm.
*   **Safe Margins (Agent Mandate):**
    *   **Keep Out Zone:** Rear 10mm of Y (Y > 310) to avoid cable chain compression.
    *   **Keep Out Zone:** Front Left (X < 10, Y < 10) during homing if not using sensorless.
*   **Max Speed:** 800mm/s (Travel).
*   **Max Accel:** 15,000mm/s² (Configured) -> 20,000mm/s² (Physical capability).

## 3. Electrical & Safety (For Monitoring Agents)
*   **System Voltage:** 
    *   **48V:** X/Y Motors (TMC5160).
    *   **24V:** Mainboard, Fans, Z-Motors, Extruder.
*   **Current Limits:**
    *   **X/Y (LDO-2504AH):** Config: 1.6A | Max Safe: 2.2A | *Warning: Monitor Driver Temp > 70C.*
    *   **Z (Tri-Z):** 1.0A.
    *   **Extruder (LGX Lite):** 0.8A (Do not exceed 0.85A to prevent motor pancake meltdown).
*   **Heaters:**
    *   **Hotend (Goliath):** Max 300C. (PT1000/Generic 3950 sensor).
    *   **Bed:** Max 130C.
    *   **Chamber:** Heater Generic (Max 100C). *Warning: Check enclosure temp if > 60C.*

## 4. Cooling Strategy
*   **Part Cooling:** CPAP (Remote 7040 Blower).
    *   *Status:* ALWAYS OFF unless printing. 
    *   *Agent Note:* If `fan_speed > 0` while idle, alert user (noise hazard).
*   **Hotend Fan:** Generic 24V. Always on > 50C.
*   **Driver Cooling:** Active 24V fans over the Octopus Pro. *Crucial for 48V/1.6A operation.*

## 5. Probing & Bed Mesh
*   **Primary Probe:** **BDsensor** (Inductive/Distance).
    *   *Location:* Nozzle Offset Y: ~27mm.
    *   *Mode:* Fast scanning.
*   **Secondary/Backup:** BTT Eddy (Currently Disabled in Config).
*   **Homing:** Sensorless X/Y (TMC5160 Diag).

## 6. Known "Quirks" (The Personality)
*   **Y-Axis Resonance:** 48-54Hz spike. *Mitigation:* Input Shaper MZV.
*   **Wiring:** Recently re-loomed. *Status:* Verify pins if "No Heater" error occurs.
*   **Endstops:** Virtual/Sensorless. *Warning:* Do not crash gantry into frame at > 100mm/s during homing debug.
