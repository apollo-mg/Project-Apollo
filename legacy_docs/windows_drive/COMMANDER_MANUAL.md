# Commander Voice Agent Manual

**Version:** 2.0 (Engineering Suite)
**Status:** Active
**Wake Words:** "Commander" (Local Control) | "Protocol Gemini" (Cloud Relay)

## Overview
The Commander is a voice-activated interface for your Klipper 3D Printer. It uses a local LLM (DeepSeek) to understand natural language and map it to engineering commands.

## Voice Commands

### 1. Status & Telemetry
*   **"Status Report"** / **"What's the printer doing?"**
    *   *Action:* Fetches bed temp, extruder temp, print percentage, and toolhead position.
*   **"Check temperatures"**
    *   *Action:* Reports current heater values.

### 2. Print History
*   **"What did I print last?"** / **"Show me the history."**
    *   *Action:* Retrieves the last 3 print jobs from Moonraker history.

### 3. Safety Controls (CRITICAL)
*   **"STOP!"** / **"Emergency Stop"**
    *   *Action:* Immediate MCU shutdown (`FIRMWARE_RESTART` equivalent). Use only in emergencies.
*   **"Pause Print"**
    *   *Action:* Pauses the current job and parks the toolhead (if configured in Klipper).
*   **"Resume Print"**
    *   *Action:* Resumes the paused job.
*   **"Cancel Print"**
    *   *Action:* Cancels the active print job and turns off heaters.

### 4. Motion & Thermal
*   **"Home all axes"** / **"Home the printer"**
    *   *Action:* Executes `G28` (Auto-Home).
*   **"Cooldown"** / **"Turn off heaters"**
    *   *Action:* Sets all heaters (Bed/Extruder) to 0°C (`TURN_OFF_HEATERS`).

## Troubleshooting
*   **"It didn't hear me"**: Watch the console. The noise floor is calibrated on startup. Ensure `Vol > Threshold`.
*   **"Backend Error"**: Check if `LM Studio` is running on port 1234.
*   **"Hallucinations"**: If the agent suggests G-code instead of acting, rephrase to be more direct (e.g., "Status" instead of "How is the machine feeling?").

## Architecture
1.  **Voice Input:** `PvRecorder` -> `Whisper (Base)` -> Text.
2.  **Reasoning:** Text -> `local_agent.ps1` -> `DeepSeek LLM` -> `COMMAND: [ACTION]`.
3.  **Execution:** `COMMAND: [ACTION]` -> `commander_voice.py` -> `Invoke-RestMethod` (Klipper API).
4.  **Feedback:** Data -> `DeepSeek LLM` (Summary) -> `Kokoro TTS` -> Audio.
