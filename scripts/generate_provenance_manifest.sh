#!/bin/bash

# Sovereign Entity Architecture - Ground Truth Provenance Manifest Generator
# This script captures the hardware and software environment provenance for
# the Apollo project, creating a reproducible environment snapshot.

set -e  # Exit on error

SCRIPT_NAME="generate_provenance_manifest.sh"
MANIFEST_FILE="${SCRIPT_NAME%.*}_manifest.txt"
TIMESTAMP=$(date +"%Y-%m-%d_%H:%M:%S")

echo "=== SOVEREIGN ENTITY ARCHITECTURE - GROUND TRUTH PROVENANCE MANIFEST ===" > "$MANIFEST_FILE"
echo "Generated: $TIMESTAMP" >> "$MANIFEST_FILE"
echo "Script: $SCRIPT_NAME" >> "$MANIFEST_FILE"
echo "================================================================" >> "$MANIFEST_FILE"
echo "" >> "$MANIFEST_FILE"

# 1. ROCm Device Information
echo "=== ROCm DEVICE INFORMATION ===" >> "$MANIFEST_FILE"
echo "Command: rocminfo" >> "$MANIFEST_FILE"
echo "--------------------------------" >> "$MANIFEST_FILE"
if command -v rocminfo >/dev/null 2>&1; then
    rocminfo >> "$MANIFEST_FILE" 2>&1 || echo "rocminfo not available" >> "$MANIFEST_FILE"
else
    echo "rocminfo not available in PATH" >> "$MANIFEST_FILE"
fi
echo "" >> "$MANIFEST_FILE"

# 2. OpenCL Device Information
echo "=== OPENCL DEVICE INFORMATION ===" >> "$MANIFEST_FILE"
echo "Command: clinfo" >> "$MANIFEST_FILE"
echo "--------------------------------" >> "$MANIFEST_FILE"
if command -v clinfo >/dev/null 2>&1; then
    clinfo >> "$MANIFEST_FILE" 2>&1 || echo "clinfo not available" >> "$MANIFEST_FILE"
else
    echo "clinfo not available in PATH" >> "$MANIFEST_FILE"
fi
echo "" >> "$MANIFEST_FILE"

# 3. Loaded Kernel Modules
echo "=== LOADED KERNEL MODULES ===" >> "$MANIFEST_FILE"
echo "Command: lsmod" >> "$MANIFEST_FILE"
echo "--------------------------------" >> "$MANIFEST_FILE"
lsmod >> "$MANIFEST_FILE" 2>&1 || echo "lsmod failed" >> "$MANIFEST_FILE"
echo "" >> "$MANIFEST_FILE"

# 4. Python Dependencies
echo "=== PYTHON DEPENDENCIES ===" >> "$MANIFEST_FILE"
echo "Command: pip freeze" >> "$MANIFEST_FILE"
echo "--------------------------------" >> "$MANIFEST_FILE"
pip freeze >> "$MANIFEST_FILE" 2>&1 || echo "pip freeze failed" >> "$MANIFEST_FILE"
echo "" >> "$MANIFEST_FILE"

echo "Provenance manifest generated: $MANIFEST_FILE"
echo "Timestamp: $TIMESTAMP"
