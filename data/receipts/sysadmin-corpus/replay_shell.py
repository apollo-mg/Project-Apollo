#!/usr/bin/env python3
"""Serve a captured machine state as a read-only shell.

WHY: the state this corpus measures is perishable -- item 1's kernel/module mismatch disappears
on the next reboot. A benchmark that needs the live machine can be run exactly once, which is not
a benchmark. This maps the commands an agent would run onto files captured while the fault was
live, so the item is replayable forever and identical for every model.

Deliberately NOT a shell emulator. It matches a command to a captured file, or refuses. A refusal
is honest ("not captured") and is recorded -- an agent that needs an uncaptured command is telling
us the capture set is incomplete, which is information about the corpus, not a scoring event.
"""
import json, re, sys, os

# command pattern -> captured file. Order matters; first match wins.
ROUTES = [
    (r"^uname\s+-r\b",                              "uname_r.txt"),
    (r"^uname\b",                                   "uname_a.txt"),
    (r"^pacman\s+-Q\s+linux",                       "pacman_kernels.txt"),
    (r"^pacman\s+-Qu\b",                            "pacman_Qu.txt"),
    (r"^pacman\s+-Qm\b",                            "pacman_Qm.txt"),
    (r"^pacman\s+-Q\s+.*keyring",                   "keyring.txt"),
    (r"^pacman\s+-Q\s+(virtualbox|kea|varnish|vinyl)", "news_packages.txt"),
    (r"^ls\s.*(/usr)?/lib/modules/?$",              "modules_dirs.txt"),
    (r"^ls\s.*/lib/modules/7\.1\.6",                "modules_running.txt"),
    (r"^lsmod\b",                                   "lsmod.txt"),
    (r"^(cat|less|head)\s+/proc/filesystems",       "proc_filesystems.txt"),
    (r"^modprobe\b",                                "modprobe_dryrun.txt"),
    (r"^lsblk\b",                                   "lsblk.txt"),
    (r"^findmnt\b.*boot",                           "findmnt_boot.txt"),
    (r"^df\b",                                      "df.txt"),
    (r"^uptime\b",                                  "uptime.txt"),
    (r"^snapper\b|^sudo\s+snapper\b",               "snapper.txt"),
    (r"^sudo\s+ls\s.*/boot|^sudo\s+find\s+/boot",   "boot_root_ls.txt"),
    (r"^ls\s.*/boot",                               "boot_user_ls.txt"),
    (r"^(sudo\s+)?find\s+/boot.*vmlinuz",           "boot_kernels.txt"),
    (r"^(sudo\s+)?find\s+/etc.*pacnew",             "pacnew.txt"),

    # --- SYS-02: DKMS build failure -------------------------------------------------
    (r"(cat|less|tail|head).*make\.log",           "make.log"),
    (r"^dkms\s+status|^sudo\s+dkms\s+status",     "dkms_status.txt"),
    # MUST require a KERNEL path. A looser pattern (any command containing both "strncpy" and
    # "string.h") mis-routed a query about the MODULE SOURCE to the kernel header on
    # 2026-08-30, handing the model the decisive evidence one turn before it asked for it.
    # A router that answers a question the agent did not ask contaminates the item.
    (r"(/lib/modules/|/usr/lib/modules/|build/include/|include/linux/).*string\.h.*strncpy|"
     r"strncpy.*(/lib/modules/|/usr/lib/modules/|build/include/|include/linux/).*string\.h|"
     r"(/lib/modules/|build/include/|include/linux/).*string\.h", "kernel_string_h_strncpy.txt"),
    (r"strscpy",                                    "kernel_string_h_strscpy.txt"),
    (r"grep.*strcpy.*fortify|fortify-string\.h",    "kernel_fortify_strcpy.txt"),
    (r"(cat|less|head|sed|grep).*nct6687\.c",       "nct6687.c.prepatch"),
    (r"dkms\s+(install|autoinstall|build)",         "dkms_build_error.txt"),
]

class ReplayShell:
    def __init__(self, state_dir):
        self.d = state_dir
        self.log = []
    def run(self, cmd):
        cmd = cmd.strip()
        for pat, fn in ROUTES:
            if re.search(pat, cmd):
                p = os.path.join(self.d, fn)
                if os.path.exists(p):
                    out = open(p, errors="replace").read()
                    self.log.append({"cmd": cmd, "matched": fn, "status": "ok"})
                    return out
        self.log.append({"cmd": cmd, "matched": None, "status": "not_captured"})
        return ("replay: this command was not captured in the recorded state.\n"
                "Available evidence covers: kernel version, installed packages, module tree,\n"
                "lsmod, /proc/filesystems, modprobe, lsblk, findmnt, df, snapper, /boot, pacnew.\n")

if __name__ == "__main__":
    sh = ReplayShell(sys.argv[1] if len(sys.argv) > 1 else "item01_kernel_module_drift/state")
    for c in sys.argv[2:]:
        print(f"$ {c}"); print(sh.run(c))
