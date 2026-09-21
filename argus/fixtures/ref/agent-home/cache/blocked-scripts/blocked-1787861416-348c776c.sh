#!/bin/bash
# Auto-saved by Hermes: this command exceeded the inline command
# parser limit and was blocked from direct execution. Review it,
# then run it via: bash /mnt/TG_2TB/Projects/Apollo/argus/fixtures/ref/agent-home/cache/blocked-scripts/blocked-1787861416-348c776c.sh
cd <redacted-home-path>; echo "U=1 (unread): $(ls cur | grep -c ',U=1')"; echo "U=2 (read): $(ls cur | grep -c ',U=2')"; echo "U=3 (deleted): $(ls cur | grep -c ',U=3')"; echo "new/ files: $(ls new 2>/dev/null | wc -l)"; echo "cur/ files: $(ls cur | wc -l)"; ls <redacted-home-path>
