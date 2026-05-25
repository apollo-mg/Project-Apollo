#!/bin/bash
pkill -f liara_indexer.py || true
nohup python3 /media/mark/TG_2TB/Apollo/Project-Apollo/tools/liara_indexer.py > /media/mark/TG_2TB/Apollo/Project-Apollo/data/liara.log 2>&1 &
echo "Liara Omnichannel Archivist started in background."
