#!/usr/bin/env python3
"""Fetch one branch of a Hugging Face repo into a directory, verifying every file.

Written 2026-09-12 for turboderp's EXL3 repos, which keep each bit-width on its own branch. The
llama-server `-hf` path cannot select a branch, and buun's native loader wants the complete snapshot
directory, so the snapshot is assembled by hand.

Each rule below comes from a real failure:
  * ONE WRITER PER DIRECTORY (flock). On 2026-09-11 two concurrent `curl -C -` writers produced a
    12 GB file 160 MB oversized, and only the sha256 check caught it.
  * Download to `.part`, verify, then rename -- a file at its final path is always a verified file.
  * LFS files are checked against the repo's published sha256 (`lfs.oid`). Small non-LFS files are
    checked by git-blob sha1 against their tree `oid`, not trusted on size alone.
  * A resume that fails verification is discarded and fetched once more from scratch; a stale
    partial must never be silently extended.

Usage:
  hf_fetch.py turboderp/Qwen3.8-27B-exl3 4.00bpw /mnt/TG_2TB/AI/Models/exl3/Qwen3.8-27B-exl3-4.00bpw
Exit status 0 only if every file verified.
"""
import fcntl, hashlib, json, os, subprocess, sys, time, urllib.request


def log(msg):
    print(time.strftime("%F %T"), msg, flush=True)


def manifest(repo, rev):
    url = f"https://huggingface.co/api/models/{repo}/tree/{rev}?recursive=true"
    with urllib.request.urlopen(url, timeout=60) as r:
        return [e for e in json.loads(r.read()) if e.get("type") == "file"]


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 24), b""):
            h.update(chunk)
    return h.hexdigest()


def git_blob_sha1(path):
    with open(path, "rb") as f:
        data = f.read()
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def verify(path, e):
    if not os.path.exists(path) or os.path.getsize(path) != e["size"]:
        return False
    lfs = (e.get("lfs") or {}).get("oid")
    return sha256(path) == lfs if lfs else git_blob_sha1(path) == e.get("oid")


def curl(url, part, resume):
    cmd = ["curl", "-sS", "-L", "--fail", "--retry", "5", "--retry-delay", "5", "-o", part, url]
    if resume:
        cmd[1:1] = ["-C", "-"]
    return subprocess.call(cmd)


def main():
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    repo, rev, out = sys.argv[1:4]
    os.makedirs(out, exist_ok=True)
    lock = open(os.path.join(out, ".hf_fetch.lock"), "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        sys.exit(f"another hf_fetch is already writing {out} -- refusing to be a second writer")

    files = manifest(repo, rev)
    log(f"{repo}@{rev}: {len(files)} files, {sum(e['size'] for e in files) / 1e9:.2f} GB -> {out}")
    bad = 0
    for e in files:
        dst = os.path.join(out, e["path"])
        os.makedirs(os.path.dirname(dst) or out, exist_ok=True)
        kind = "sha256" if (e.get("lfs") or {}).get("oid") else "git-blob"
        if verify(dst, e):
            log(f"  ok, already verified ({kind})  {e['path']}")
            continue
        part = dst + ".part"
        url = f"https://huggingface.co/{repo}/resolve/{rev}/{e['path']}"
        ok = False
        for attempt, resume in ((1, os.path.exists(part)), (2, False)):
            if not resume and os.path.exists(part):
                os.remove(part)
            rc = curl(url, part, resume)
            if rc == 0 and verify(part, e):
                ok = True
                break
            log(f"  attempt {attempt} ({'resume' if resume else 'fresh'}) failed: curl rc={rc}, "
                f"size {os.path.getsize(part) if os.path.exists(part) else 0:,d} of {e['size']:,d}")
        if not ok:
            log(f"  FAILED  {e['path']}  (partial kept as .part for inspection)")
            bad += 1
            continue
        os.replace(part, dst)
        log(f"  VERIFIED ({kind})  {e['path']}  {e['size']:,d} B")
    log("ALL FILES VERIFIED" if not bad else f"{bad} FILE(S) FAILED -- snapshot is NOT usable")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
