#!/usr/bin/env python3
"""Replay shell that models EDITS, not just state.

WHY THIS EXISTS: the first harness served a fixed snapshot. On SYS-02 that made the item
unwinnable in a way that flattered the grader — the signal that rescued Claude was the compiler
error moving from line 444 to 445 after applying the (wrong) suggested #include. A snapshot
server replays line 444 forever, so the agent can never observe that its fix changed nothing.
The item measured "did you check the kernel headers unprompted" and was structurally blind to
self-correction, which is the more interesting capability.

Model: the agent's edits move a small state machine. Commands are answered from the state the
agent has actually put the machine in.

  SRC_PREPATCH   -- as found
  SRC_INCLUDE    -- after adding #include <linux/string.h>   (the compiler's own suggestion)
  SRC_STRSCPY    -- after replacing strncpy with strscpy      (correct)

A build in each state returns that state's REAL captured make.log. Nothing is synthesised.
"""
import re, os, sys

SRC_PREPATCH, SRC_INCLUDE, SRC_STRSCPY = "prepatch", "includeonly", "strscpy"

class StatefulReplay:
    def __init__(self, state_dir):
        self.d = state_dir
        self.src = SRC_PREPATCH
        self.log = []

    # --- edit detection -------------------------------------------------------
    # Deliberately generous: sed/python/cat-heredoc/patch all count. We are testing
    # diagnosis, not whether the agent guessed our preferred editor.
    def _apply_edit(self, cmd):
        low = cmd.lower()
        wrote_strscpy = "strscpy" in low
        wrote_include = ("string.h" in low and "#include" in low) or \
                        ("string.h" in low and re.search(r"\bsed\b|\bawk\b|>>|tee", low))
        if wrote_strscpy:
            self.src = SRC_STRSCPY; return "edited: strncpy -> strscpy"
        if wrote_include:
            self.src = SRC_INCLUDE; return "edited: added #include <linux/string.h>"
        return None

    def run(self, cmd):
        cmd = cmd.strip()
        if re.search(r"\b(sed -i|tee |patch |python3? -|cat >)", cmd) or ">>" in cmd:
            note = self._apply_edit(cmd)
            if note:
                self.log.append({"cmd": cmd, "matched": f"EDIT->{self.src}", "status": "edit"})
                return f"(edit applied)\n"

        # a build reflects whatever state the source is actually in
        if re.search(r"dkms\s+(build|install|autoinstall)|make\b", cmd):
            fn = {SRC_PREPATCH:  "make.log.state1_prepatch",
                  SRC_INCLUDE:   "make.log.state2_includeonly",
                  SRC_STRSCPY:   "make.log.state3_strscpy"}[self.src]
            self.log.append({"cmd": cmd, "matched": fn, "status": "ok", "src_state": self.src})
            return open(os.path.join(self.d, fn), errors="replace").read()

        # reading the module source returns the CURRENT state
        if re.search(r"nct6687\.c", cmd):
            fn = {SRC_PREPATCH: "nct6687.c.prepatch",
                  SRC_INCLUDE:  "nct6687.c.includeonly",
                  SRC_STRSCPY:  "nct6687.c.fixed"}[self.src]
            self.log.append({"cmd": cmd, "matched": fn, "status": "ok", "src_state": self.src})
            return open(os.path.join(self.d, fn), errors="replace").read()

        for pat, fn in [(r"dkms\s+status", "dkms_status.txt"),
                        (r"(include/linux/|lib/modules/).*string\.h", "kernel_string_h_strncpy.txt"),
                        (r"strscpy", "kernel_string_h_strscpy.txt"),
                        (r"fortify|strcpy\b", "kernel_fortify_strcpy.txt"),
                        (r"uname", "uname_r.txt")]:
            if re.search(pat, cmd):
                p = os.path.join(self.d, fn)
                if os.path.exists(p):
                    self.log.append({"cmd": cmd, "matched": fn, "status": "ok"})
                    return open(p, errors="replace").read()
        self.log.append({"cmd": cmd, "matched": None, "status": "not_captured"})
        return "replay: command not captured.\n"

if __name__ == "__main__":
    sh = StatefulReplay(sys.argv[1])
    for c in sys.argv[2:]:
        print(f"$ {c}"); print(sh.run(c)[:400])
