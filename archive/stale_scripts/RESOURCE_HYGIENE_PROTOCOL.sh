#!/bin/bash
# Apollo Resource Hygiene Protocol
# Purpose: Prevent local storage bloat from telemetry and debris.

LOG_DIR="/var/log"
DOCKER_DIR="/var/lib/docker"
RETENTION_DAYS=7

echo "[Apollo] Starting Resource Hygiene Protocol..."

# 1. Clean up old logs
if [ -d "$LOG_DIR" ]; then
    echo "[Apollo] Cleaning logs older than $RETENTION_DAYS days in $LOG_DIR"
    find $LOG_DIR -type f -name "*.log.*" -mtime +$RETENTION_DAYS -exec rm -f {} \;
    find $LOG_DIR -type f -name "*.log" -mtime +$RETENTION_DAYS -exec rm -f {} \;
fi

# 2. Docker Cleanup (if exists)
if [ -d "$DOCKER_DIR" ]; then
    echo "[Apollo] Cleaning Docker debris..."
    docker system prune -af --volumes
fi

# 3. Check for large abandoned files in /tmp
echo "[Apollo] Checking /tmp for large debris..."
find /tmp -type f -size +100M -mtime +$RETENTION_DAYS -exec rm -f {} \;

echo "[Apollo] Hygiene Protocol Complete."
