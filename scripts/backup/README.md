# NAS backup

Nightly copy of everything that is **not** model-sized or regenerable, to
`//10.0.0.43/mgalyan` → `/mnt/HDD/apollo-backup`.

## Why

The Apollo repo tracks `engines/` as **submodules** — it stores pointers, not code. If an upstream
fork were deleted and this disk failed, the code would be gone. That stopped being hypothetical on
2026-09-02: `ggml.ai` joined Hugging Face in Feb 2026, and NVIDIA is acquiring Hugging Face (closing
H1 2027). Upstream availability is no longer a safe assumption, and Tom describes his own fork's
future as "unplanned as of yet."

## What it backs up

| | size |
|---|---|
| curated working tree — receipts, notes, dev diaries, Apollo Docs, vault/skills, scripts, modules, tools, profiles.yaml | ~189 MB |
| `git bundle --all` of **22 repos** (Apollo + every engine), full history, one file each | ~3.4 GB |

Skipped: models (404 GB), venvs, build artifacts, archives — all large and replaceable.

Bundles regenerate **only when HEAD moves** (`.head` stamp files), so an unchanged night costs
~12 seconds instead of pushing 3.4 GB over CIFS.

## Safety

The script **aborts if `/mnt/HDD` is not mounted.** Without that, rsync would happily write into the
empty mountpoint directory, filling the local disk while appearing to succeed — a backup that looks
fine until you need it.

## Setup (already done 2026-09-09)

Automount via `/etc/fstab`:
```
//10.0.0.43/mgalyan /mnt/HDD cifs credentials=/etc/samba/nas-mgalyan.cred,uid=1000,gid=1000,\
iocharset=utf8,_netdev,nofail,x-systemd.automount,x-systemd.idle-timeout=600 0 0
```
`x-systemd.automount` mounts on first access rather than at boot; `nofail` means a NAS outage never
blocks startup. Credentials live in `/etc/samba/nas-mgalyan.cred` (root, mode 600) — **never** in
fstab, which is world-readable.

Timer: `systemctl --user enable --now apollo-nas-backup.timer` (03:42 nightly, `Persistent=true`).
Requires `loginctl enable-linger mark` so it fires without an active session — already set.

Note: after adding the fstab line, `daemon-reload` *generates* the unit but does not start it.
`sudo systemctl start mnt-HDD.automount` is needed once for the current boot.

## Verified, not assumed

Restore-tested 2026-09-09: cloned `engine-buun-llama-cpp.bundle` into a temp dir —
HEAD `3823c9eb6…` matched the original, **11,804 commits** intact, and commit `a56eeef5` (the
tensor-split cache fix verified on the P100s) present in the restored history.

Cold-start tested: `systemctl stop`/`start mnt-HDD.automount`, then ran the script. The automount
fired on access and the run completed in 12 s.
