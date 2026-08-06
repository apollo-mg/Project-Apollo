# Runbook — Clone Kubuntu OS (HDD → 512G Optane), coexist with models

**Node:** `ai-p100-sli` (`mark@10.0.0.73`) · Dual-P100 SLI · Gigabyte Z370XP SLI · **no IPMI**
**Goal:** move the OS off the Samsung 640G HDD (`sdb`) onto the fast Intel H10 512G Optane
(`nvme1n1`), keeping the 190G of models on that same Optane, then pull `sdb` for the Alienware.
**Boot mode:** UEFI + Secure Boot (shim). **Firmware target of every write below: `/dev/nvme1n1` ONLY.**

## Ground truth (verified 2026-07-24, read-only)

| Device | Model | Size | Now | Fate |
|---|---|---|---|---|
| `sdb` | SAMSUNG HM640JJ (HDD, GPT) | 640G | `sdb1`=ESP `/boot/efi` (300M), `sdb2`=`/` (37G used, label `kubuntu_2604`) | **SOURCE** → pulled → Alienware |
| `sda` | ST9500325AS (HDD, MBR) | 500G | `sda1`=`/mnt/HDD` (118G used, 317G free) | **UNTOUCHED** — protected data drive + backup staging |
| `nvme1n1` | INTEL HBRPEKNX0202AH (H10 QLC) | 477G | `nvme1n1p1`=`/mnt/models` (190G used) | **TARGET** → `[ESP][root][models]` |
| `nvme0n1` | INTEL MEMPEK1W032GA (Optane 32G) | 27G | `/mnt/optane` (+swapfile) | not involved |

Current UUIDs (source of the fstab rewrites): root `684ca0c1-bcc8-4d34-a867-df935493b5eb`,
ESP `4F98-D056`, models `0861c2ec-ed52-4e8d-b204-2d8fa668b77c`.
Keep unchanged: `/mnt/HDD` `352277f4-…` (sda), `/mnt/optane` `85420c15-…` (nvme0n1).
Existing NVRAM: `Boot0003 Kubuntu` → sdb ESP (`\EFI\UBUNTU\SHIMX64.EFI`). Leave it until the very end.

## Safety invariants (read before every phase)

1. **Only `sdb` runs the OS until the Optane boots cleanly several times.** Every step except the
   boot-test (Phase 6) is non-fatal to uptime — the live OS keeps running on `sdb` throughout.
2. **Never `parted`/`mkfs`/`wipefs` anything but `/dev/nvme1n1`.** Re-run `lsblk` and eyeball the model
   string (`INTEL HBRPEKNX0202AH`) immediately before any destructive Optane command.
3. **The 190G backup must exist and be verified before Phase 2 touches the Optane.**
4. **Phase 6+ (boot-test / HDD removal) only with you physically at the box** (no remote recovery).
5. Root steps need `sudo`; run them yourself at the box. Paste output back at each **GATE** — I verify
   before you proceed.

---

## Phase 0 — Pause the live AgentWorld campaign (frees RAM, releases /mnt/models)

The Optane is live-mmapped by the AgentWorld server (`:8082`), so it can't be unmounted until that stops.

```bash
pgrep -af llama-server                 # confirm the pid(s) — expect the AgentWorld server on :8082
kill <server_pid> <wrapper_pid>        # stop it (it was launched manually via tee, not systemd)
ss -ltnp | grep 8082 || echo "port 8082 closed"
sudo fuser -m /mnt/models              # GATE: must print NOTHING (nobody holding the mount)
```

## Phase 1 — Back up 190G models → /mnt/HDD (safe; /mnt/models stays mounted, read-only source)

```bash
sudo mkdir -p /mnt/HDD/models_backup_20260724
sudo rsync -aHAX --numeric-ids --info=progress2 /mnt/models/ /mnt/HDD/models_backup_20260724/
# GATE — verify the copy before we destroy the original:
du -sh /mnt/models /mnt/HDD/models_backup_20260724            # sizes should match (~190G)
sudo rsync -aHAXn --checksum /mnt/models/ /mnt/HDD/models_backup_20260724/ | head   # dry-run: ~nothing to copy
```

## Phase 2 — Repartition the Optane (destructive to Optane ONLY; OS still live on sdb)

```bash
lsblk -dn -o NAME,SIZE,MODEL /dev/nvme1n1     # CONFIRM: INTEL HBRPEKNX0202AH, 477G  <-- STOP if not
sudo umount /mnt/models
sudo wipefs -a /dev/nvme1n1
sudo parted -s /dev/nvme1n1 mklabel gpt
sudo parted -s /dev/nvme1n1 mkpart ESP   fat32 1MiB   513MiB
sudo parted -s /dev/nvme1n1 set 1 esp on
sudo parted -s /dev/nvme1n1 mkpart root  ext4  513MiB 231GiB
sudo parted -s /dev/nvme1n1 mkpart models ext4 231GiB 100%
sudo mkfs.fat -F32           /dev/nvme1n1p1
sudo mkfs.ext4 -L kubuntu_root /dev/nvme1n1p2
sudo mkfs.ext4 -L models       /dev/nvme1n1p3
```

## Phase 3 — Restore models + clone the OS (live rsync, run root-copy twice)

```bash
# models -> new p3
sudo mkdir -p /mnt/newmodels && sudo mount /dev/nvme1n1p3 /mnt/newmodels
sudo rsync -aHAX --numeric-ids --info=progress2 /mnt/HDD/models_backup_20260724/ /mnt/newmodels/

# OS root -> new p2  (exclude virtual fs, other mounts, swapfile)
sudo mkdir -p /mnt/newroot && sudo mount /dev/nvme1n1p2 /mnt/newroot
sudo rsync -aHAX --numeric-ids --info=progress2 \
  --exclude={"/proc/*","/sys/*","/dev/*","/run/*","/tmp/*","/mnt/*","/media/*","/lost+found","/swapfile"} \
  / /mnt/newroot/
sudo rsync -aHAX --numeric-ids --info=progress2 \
  --exclude={"/proc/*","/sys/*","/dev/*","/run/*","/tmp/*","/mnt/*","/media/*","/lost+found","/swapfile"} \
  / /mnt/newroot/          # 2nd pass catches changes since 1st

# ESP -> new p1
sudo mount /dev/nvme1n1p1 /mnt/newroot/boot/efi
sudo rsync -aHAX /boot/efi/ /mnt/newroot/boot/efi/
```

## Phase 4 — Rewrite fstab on the new root (the #1 cause of a clone that won't boot)

```bash
sudo blkid /dev/nvme1n1p1 /dev/nvme1n1p2 /dev/nvme1n1p3   # note NEW UUIDs
sudoedit /mnt/newroot/etc/fstab
```
In `/mnt/newroot/etc/fstab`, replace ONLY the sdb-based lines with the NEW UUIDs:
- `/` : old `684ca0c1-…` → **new p2 UUID**
- `/boot/efi` : old `4F98-D056` → **new p1 UUID**
- `/mnt/models` : old `0861c2ec-…` → **new p3 UUID**
- Leave `/mnt/HDD` (`352277f4-…`) and `/mnt/optane` (`85420c15-…`) as-is.
- Swap: recreate on the new root, then keep the `/swapfile` line —
  `sudo fallocate -l 4G /mnt/newroot/swapfile && sudo chmod 600 /mnt/newroot/swapfile && sudo mkswap /mnt/newroot/swapfile`
  (or comment the `/swapfile swap` line if you don't want it).

## Phase 5 — Install GRUB into the new ESP via chroot (Secure Boot safe)

```bash
for d in dev dev/pts proc sys run; do sudo mount --bind /$d /mnt/newroot/$d; done
sudo chroot /mnt/newroot /bin/bash
  # inside chroot:
  grub-install --target=x86_64-efi --efi-directory=/boot/efi --bootloader-id=kubuntu-optane
  grub-install --target=x86_64-efi --efi-directory=/boot/efi --removable   # \EFI\BOOT\BOOTX64.EFI fallback insurance
  update-grub
  exit
# unmount in reverse
sudo umount /mnt/newroot/boot/efi
for d in run sys proc dev/pts dev; do sudo umount /mnt/newroot/$d; done
sudo umount /mnt/newmodels /mnt/newroot
```

## Phase 6 — Self-reverting boot test  ⚠️ PHYSICALLY AT THE BOX

```bash
sudo efibootmgr -v            # find the "kubuntu-optane" entry number, e.g. 0005
sudo efibootmgr --bootnext 0005
sudo reboot
```
BootNext fires **once**. If the Optane hangs, just power-cycle → firmware falls back to `sdb`
(`Boot0003 Kubuntu`). After it comes up:
```bash
findmnt /                    # MUST show /dev/nvme1n1p2  (booted from Optane)
findmnt /mnt/models          # /dev/nvme1n1p3
lsblk -e7 -o NAME,SIZE,MOUNTPOINT,MODEL
```
Repeat the `--bootnext` test 2–3 times; confirm stable.

## Phase 7 — Commit, then pull the HDD  ⚠️ AT THE BOX

```bash
sudo efibootmgr -o <optane>,0003        # prefer Optane, keep sdb (0003) as fallback for now
# do a few NORMAL reboots (no bootnext) -> confirm it defaults to the Optane
sudo poweroff
# --- physically remove sdb (Samsung HM640JJ) ---
# boot, then:
findmnt / ; findmnt /mnt/models ; findmnt /mnt/HDD    # all present, root = nvme1n1p2
sudo efibootmgr -b 0003 -B               # optional: delete the now-dead sdb Kubuntu NVRAM entry
```
`sdb` → Alienware Alpha R1. Keep `/mnt/HDD/models_backup_20260724` until you're satisfied, then reclaim it.

---

### Failure recovery cheatsheet
- **Optane won't boot / hangs:** power-cycle → boots `sdb` automatically (BootNext is one-shot; sdb still in BootOrder). Nothing lost.
- **Boots but drops to initramfs `(initramfs)`:** almost always a bad fstab UUID (Phase 4). Boot back to sdb, re-check `blkid` vs `/mnt/newroot/etc/fstab`.
- **"No bootable device":** firmware didn't pick up the new entry — the `--removable` fallback (`\EFI\BOOT\BOOTX64.EFI`) should still boot; else re-run Phase 5 `grub-install`.
- **Models missing after boot:** `/mnt/models` fstab UUID wrong or p3 not mounted; data is safe in `/mnt/HDD/models_backup_20260724`.

---

# AS EXECUTED — 2026-07-24 (supersedes Phases 2–3 above)

**Method changed: shrink-in-place instead of wipe-and-restore.** The models were never deleted, so two
copies existed at all times (Optane original + verified HDD backup). Faster and strictly safer.

### Completed & verified

| Phase | Result |
|---|---|
| 0 — quiesce | AgentWorld `llama-server` (:8082) killed (needed SIGKILL to release the P100 mmap). `/mnt/models` released. |
| 1 — backup | 190G → `/mnt/HDD/models_backup_20260724`. **Verified byte-exact: 203,702,762,820 == 203,702,762,820**, 11==11 files, per-GGUF sizes identical, rsync log clean. |
| 2 — reshape | `e2fsck` clean → `resize2fs` to 240GiB (62,914,560 blocks; fs was 0.0% non-contiguous so relocation was trivial) → `resizepart` p1 to 246,272MiB → created p2 ESP 512MiB + p3 root ~236GiB → mkfs. **Models re-mounted, all files intact.** |
| 3 — clone | `rsync -aHAXx` (one-file-system) ×2 passes + ESP copy. 36G. Both kernels present. All exit 0. |
| 4 — fstab | `/` → `9859ee68-061a-482c-ad6e-30cca2505a9a`, `/boot/efi` → `D075-7C82`. Backup at `/etc/fstab.pre-optane-clone`. 512M swapfile recreated. |
| 5 — grub | `grub-install` (id `kubuntu-optane`) + `--removable` fallback + `update-grub`. Stub and grub.cfg both point at the NEW root UUID. |
| 5b — NVRAM | `Boot0002* kubuntu-optane` → PARTUUID `c505934c-…` (p2). **BootOrder deliberately left `0003,0002,0001,0000` (sdb first) so a failed test auto-reverts.** |

### Final Optane layout (physical order differs from the original plan; functionally identical)
```
nvme1n1p1  240.5G  ext4  models        /mnt/models   (UUID 0861c2ec-… UNCHANGED — shrink preserved it)
nvme1n1p2    512M  vfat  ESP           /boot/efi     (UUID D075-7C82)
nvme1n1p3  235.9G  ext4  kubuntu_root  /             (UUID 9859ee68-…)
```

### Gotchas hit (worth remembering)
1. **`parted -s` refuses to shrink a partition** — it demands interactive confirmation and exits 1 *without
   changing anything*. Workaround: `echo Yes | parted ---pretend-input-tty …`.
2. **`mount --bind /sys` does not carry the nested `efivarfs` submount into a chroot**, so `grub-install`
   warns *"EFI variables cannot be set"* and creates **no NVRAM entry**. Fix: run `efibootmgr --create`
   from the live system afterwards (or use `--rbind`).
3. **The ESP stub `grub.cfg` still pointed at the OLD root UUID** after a raw ESP copy — booting it would
   have silently booted the old HDD and made the migration look like it worked. `grub-install` fixes it.
4. **`rsync --exclude=/mnt/*` leaves `/mnt` empty on the clone**, so fstab mountpoint dirs
   (`models`, `HDD`, `optane`) must be re-created by hand.
5. **`lsinitramfs` without sudo silently returns nothing** (looks like "no nvme driver!"). Verified with
   sudo: `nvme.ko`/`nvme-core.ko`/`ext4` all present, `MODULES=most` — Optane root is reachable at boot.

### Phase 6 — boot test: **PASSED FIRST TRY**
`BootNext=0002` → booted straight into the Optane. `/`=`nvme1n1p3`, `/boot/efi`=`nvme1n1p2`,
`/mnt/models`=`nvme1n1p1`, `/mnt/HDD`=`sda1`. No failed services. Both swaps active. BootNext self-cleared.

### Phase 6b — stale ESP stub (caught post-boot, would have broken Phase 7)
Firmware auto-created `Boot0004* ubuntu` pointing at the **new** ESP via `\EFI\UBUNTU\SHIMX64.EFI`.
That directory was rsynced verbatim from sdb, so its stub still read
`search.fs_uuid 684ca0c1-… root hd1,gpt2` — i.e. it would have booted the **old HDD**, and after sdb's
removal would have dropped to `grub rescue`. Fixed by rewriting the stub to the new root UUID.
**All three ESP boot paths now resolve to the Optane** (`kubuntu-optane/`, `ubuntu/`, `BOOT/` fallback);
zero references to the old root remain on the ESP.

### Phase 7 — default-boot confirmation: **PASSED**
`BootOrder` set to `0002,0003,…` (Optane first, HDD retained as fallback). A normal reboot with **no
BootNext** came up `BootCurrent: 0002` from `nvme1n1p3` — the box now boots the Optane unassisted.

### Models integrity after `resize2fs`: **VERIFIED THREE WAYS**
1. `rsync -rcn` full 190G compare vs backup → **zero differences**, exit 0 (~30 min runtime).
2. Independent `md5sum` of `mmproj-F16.gguf` → identical both sides (`051423f7…`).
3. **Canary test** → planting a file produced `DIFF .canary`, proving the comparison actually
   detects differences (a clean result from an inert check would be worthless). Canary removed;
   backup back to exactly 11 files.

### REMAINING (physical, at the box)
```bash
sudo poweroff          # then remove the Samsung HM640JJ (sdb) -> Alienware Alpha R1
# after booting without it:
findmnt / ; findmnt /mnt/models ; findmnt /mnt/HDD
sudo efibootmgr -b 0003 -B     # optional: delete the now-dead sdb NVRAM entry
```
Keep `/mnt/HDD/models_backup_20260724` (190G) until satisfied, then reclaim the space.

**Gotcha #6 for the list:** a background check that leaves artifacts behind (my canary) must clean up
even when the connection dies mid-run — verify the cleanup happened rather than assuming it did.

