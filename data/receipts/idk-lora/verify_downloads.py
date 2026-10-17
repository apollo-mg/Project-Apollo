#!/usr/bin/env python3
"""Verify every LFS file of a downloaded Hugging Face repo against the sha256 the Hub publishes (lfs.oid).
Usage: verify_downloads.py REPO LOCAL_DIR [SUBPATH]   -> prints one line per file and OK/FAIL; exit 1 on any mismatch."""
import hashlib, json, sys, urllib.request
from pathlib import Path

repo, local = sys.argv[1], Path(sys.argv[2]); sub = sys.argv[3] if len(sys.argv) > 3 else ""
tree = json.loads(urllib.request.urlopen(f"https://huggingface.co/api/models/{repo}/tree/main/{sub}?recursive=1").read())
bad = 0
for f in tree:
    if f.get("type") != "file" or "lfs" not in f: continue
    p = local / f["path"]
    if not p.exists(): print("MISSING", f["path"]); bad += 1; continue
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 24), b""): h.update(chunk)
    ok = h.hexdigest() == f["lfs"]["oid"] and p.stat().st_size == f["lfs"]["size"]
    print("OK  " if ok else "FAIL", f["path"], f["lfs"]["size"]); bad += not ok
print("ALL_OK" if not bad else f"{bad} PROBLEM(S)")
sys.exit(1 if bad else 0)
