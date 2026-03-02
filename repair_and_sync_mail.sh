#!/bin/bash
# repair_and_sync_mail.sh: Robust mbsync retrier for Gmail

# Paths to potential journal files
INBOX_JOURNAL="/home/mark/.mail/gmail/INBOX/.mbsyncstate.journal"
SENT_JOURNAL="/home/mark/.mail/gmail/[Gmail].Sent Mail/.mbsyncstate.journal"

echo "--- Starting robust email synchronization ---"

until mbsync -aV; do
    ret=$?
    echo "--- mbsync failed with exit code $ret, checking for corruption ---"
    
    # Remove journals if they exist to prevent 'incomplete journal entry' errors
    if [ -f "$INBOX_JOURNAL" ]; then
        echo "Removing corrupted INBOX journal..."
        rm -f "$INBOX_JOURNAL"
    fi
    if [ -f "$SENT_JOURNAL" ]; then
        echo "Removing corrupted Sent Mail journal..."
        rm -f "$SENT_JOURNAL"
    fi
    
    echo "Waiting 30 seconds before retry..."
    sleep 30
done

echo "--- SUCCESS: Email synchronization complete! ---"
