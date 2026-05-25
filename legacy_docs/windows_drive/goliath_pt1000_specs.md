# TECHNICAL REFERENCE: Goliath Hotend & PT1000 Sensor
**System:** Ender 6 Vz-Hybrid
**Last Verified:** Feb 14, 2026

## 1. Hotend Specs (Goliath)
*   **Max Temperature:** 300C (Safe continuous).
*   **Heater:** 24V / 65W.
*   **Cooling:** Water-cooled or high-airflow CPAP remote blower.

## 2. Sensor Specs (PT1000)
*   **Type:** Resistance Temperature Detector (RTD).
*   **Klipper Config:** `sensor_type: PT1000`.
*   **Pull-up Resistor:** Typically 4.7k on BTT Octopus Pro.
*   **Accuracy:** High precision, linear scaling compared to standard thermistors.

## 3. Maintenance Notes
*   Ensure the heatbreak is properly seated to prevent leakage at 280C+ temperatures.
*   PT1000 wiring must be secure; loose connections will cause huge temperature swings in Klipper.
