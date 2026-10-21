#!/usr/bin/env bash

cd "$(dirname "$0")"

DRIFT_FILE="DRIFT_WARNING.md"
rm -f "$DRIFT_FILE"

echo "========================================="
echo "🔬 Running SMVP Boot Diagnostics..."
echo "========================================="

# SMVP is SKIPPED while the orchestration layer is dormant (STATUS.md; Mark, 2026-10-21). It called .73:8082 directly,
# an endpoint that no longer exists, and its error text was cut at 100 chars before "EHOSTUNREACH", so the offline
# branch never matched: 54 of 54 logged runs wrote a DRIFT_WARNING that meant nothing. An alarm that always fires
# trains agents to ignore the channel. Set APOLLO_SMVP=1 (or create run/smvp.enable) when the layer is revived.
if [ "${APOLLO_SMVP:-0}" != 1 ] && [ ! -f run/smvp.enable ]; then
    echo "⏭️  SMVP skipped: orchestration layer dormant (STATUS.md). APOLLO_SMVP=1 or run/smvp.enable to run it."
    OUTPUT="SMVP_SKIPPED"
else
    # Execute the diagnostic runner using tsx
    OUTPUT=$(npx --yes tsx engines/open-multi-agent/examples/diagnostic_runner.ts 2>&1)
fi

if [ "$OUTPUT" = "SMVP_SKIPPED" ]; then
    :
elif echo "$OUTPUT" | grep -q "DIAGNOSTIC_SUCCESS"; then
    echo "✅ SMVP Verification Passed. No drift detected."
elif echo "$OUTPUT" | grep -q "EHOSTUNREACH"; then
    echo "⚠️  SMVP Verification Skipped: FLEET_OFFLINE (EHOSTUNREACH detected)."
    echo "The remote LLM node is currently powered off. No architectural drift detected."
else
    echo "❌ SMVP Verification Failed! Logging architectural drift warning."
    echo "The internal schema or tools failed to execute during boot. See logs for details."
    echo "OUTPUT TRACE:"
    echo "$OUTPUT"
    
    cat << 'EOF' > "$DRIFT_FILE"
The automated SMVP diagnostic suite failed during boot. This means the Sovereign Engine's current tool schema or endpoint connection is broken.
A native tool (like `web_search`) failed to execute or return the expected output.
You MUST investigate the codebase or API endpoints to reconcile this architectural drift before proceeding with standard tasks.
EOF
fi

# --- ledger subsystem health -------------------------------------------------
# The periodic dev-diary can fail SILENTLY: cron stops, an endpoint moves, a session id
# changes, and nobody notices until the context is needed days later. Its heartbeat is
# checked here so a stale ledger routes into DRIFT_WARNING.md -- the one channel agents
# already must resolve at session start. Appends AFTER the SMVP block so it adds to,
# rather than replaces, any drift already logged above.
echo
echo "🔎 Ledger subsystem..."
./tools/ledger_health.sh || true
