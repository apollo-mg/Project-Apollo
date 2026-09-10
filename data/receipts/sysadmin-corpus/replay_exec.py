#!/usr/bin/env python3
"""Replay shell that ACTUALLY EXECUTES read-only text commands against captured files.

WHY: the previous harness matched a regex and returned whole captured files. A model asking
`sed -n '444p' file | wc -c` got the file's first line onward -- the same 1700-line blob every
time. On 2026-09-02 that put Qwen3.8-27B into an 11-turn identical-command loop: it asked a
precise question, got an irrelevant answer, varied the phrasing, got the same answer, and at
temperature 0 had no way out. That was recorded as "degenerate looping" and blamed on the model.
It was the harness feeding it noise.

Design: rewrite paths to point at the captured file for the CURRENT state, then really run the
pipeline. Read-only text tools only, whitelisted per pipeline segment, timeout, temp CWD.
"""
import re, os, sys, shlex, subprocess, tempfile

SRC_PREPATCH, SRC_INCLUDE, SRC_STRSCPY = "prepatch", "includeonly", "strscpy"
ALLOWED = {"ls","sed","grep","egrep","fgrep","awk","head","tail","wc","cat","cut","sort","uniq",
           "od","xxd","tr","nl","echo","true","rev","column","diff","file","stat","basename"}

def _split_pipeline(cmd):
    """Split on | that is OUTSIDE quotes. A naive cmd.split("|") breaks grep alternation
    (grep -n 'strncpy\\|strcmp') into fragments that fail the whitelist."""
    segs, cur, q = [], [], None
    i = 0
    while i < len(cmd):
        c = cmd[i]
        if q:
            cur.append(c)
            if c == q: q = None
        elif c in "\'\"":
            q = c; cur.append(c)
        elif c == "\\" and i + 1 < len(cmd):
            cur.append(c); cur.append(cmd[i+1]); i += 1
        elif c == "|":
            segs.append("".join(cur)); cur = []
        else:
            cur.append(c)
        i += 1
    segs.append("".join(cur))
    return [x for x in segs if x.strip()]


class ExecReplay:
    def __init__(self, state_dir):
        self.d = os.path.abspath(state_dir); self.src = SRC_PREPATCH; self.log = []
        self.tmp = tempfile.mkdtemp(prefix="replay_")

    def _srcfile(self):
        return os.path.join(self.d, {SRC_PREPATCH:"nct6687.c.prepatch",
                                     SRC_INCLUDE:"nct6687.c.includeonly",
                                     SRC_STRSCPY:"nct6687.c.fixed"}[self.src])
    def _buildlog(self):
        return os.path.join(self.d, {SRC_PREPATCH:"make.log.state1_prepatch",
                                     SRC_INCLUDE:"make.log.state2_includeonly",
                                     SRC_STRSCPY:"make.log.state3_strscpy"}[self.src])

    def _rewrite(self, cmd):
        """Point real paths at captured files. Order matters: longest first."""
        # ONE pass with alternation. Three sequential subs re-matched inside the path they had
        # just written (nct6687.c.prepatch contains nct6687.c), producing a doubled path.
        src = self._srcfile()
        cmd = re.sub(r"/var/lib/dkms/nct6687d/1/build/nct6687\.c"
                     r"|/usr/src/nct6687d-1/nct6687\.c"
                     r"|(?<![\w./])nct6687\.c(?![\w.])",
                     lambda m: src, cmd)
        cmd = re.sub(r"/var/lib/dkms/nct6687d/1/build/make\.log", self._buildlog(), cmd)
        # The REAL header, 588 lines. Previously this pointed at pre-filtered grep OUTPUT, so a
        # model that ran `cat string.h` or `grep -c` got 5 result lines masquerading as the file.
        cmd = re.sub(r"/(usr/)?lib/modules/[^/\s]+/build/include/linux/string\.h",
                     os.path.join(self.d, "kernel_string.h"), cmd)
        return cmd

    def _safe(self, cmd):
        """Every pipeline segment must start with a whitelisted read-only tool."""
        if re.search(r"[;&`]|\$\(|>\s*/(?!dev/null)", cmd):
            return False, "shell metacharacters or redirection to a real path"
        for seg in _split_pipeline(cmd):
            try: toks = shlex.split(seg)
            except ValueError: return False, "unparseable"
            if not toks: return False, "empty segment"
            name = os.path.basename(toks[0].removeprefix("sudo"))
            if toks[0] == "sudo": 
                toks = toks[1:]
                if not toks: return False, "empty after sudo"
                name = os.path.basename(toks[0])
            if name not in ALLOWED: return False, f"'{name}' not in the read-only whitelist"
        return True, ""

    def _apply_edit(self, cmd):
        low = cmd.lower()
        if "strscpy" in low: self.src = SRC_STRSCPY; return True
        if "string.h" in low: self.src = SRC_INCLUDE; return True
        return False

    def run(self, cmd):
        cmd = cmd.strip()
        # edits move the state machine (sed -i / tee / patch / heredoc)
        if re.search(r"\bsed\s+-i|\btee\b|\bpatch\b|cat\s*>", cmd) or ">>" in cmd:
            if self._apply_edit(cmd):
                self.log.append({"cmd":cmd,"matched":f"EDIT->{self.src}","status":"edit"})
                return "(edit applied)\n"
        # a build reflects whatever state the source is in
        if re.search(r"dkms\s+(build|install|autoinstall)|(^|\s)make(\s|$)", cmd):
            self.log.append({"cmd":cmd,"matched":os.path.basename(self._buildlog()),
                             "status":"ok","src_state":self.src})
            return open(self._buildlog(), errors="replace").read()
        if re.search(r"dkms\s+status", cmd):
            p=os.path.join(self.d,"dkms_status.txt")
            self.log.append({"cmd":cmd,"matched":"dkms_status.txt","status":"ok"})
            return open(p, errors="replace").read()
        if re.match(r"\s*(sudo\s+)?ls\b", cmd):
            KNOWN = {"/var/lib/dkms": "ls_dkms.txt",
                     "/var/lib/dkms/nct6687d": "ls_dkms.txt",
                     "/var/lib/dkms/nct6687d/1": "ls_dkms_build.txt",
                     "/var/lib/dkms/nct6687d/1/build": "ls_dkms_build.txt",
                     "/usr/src/nct6687d-1": "ls_dkms_build.txt"}
            m = re.findall(r"(/[\w./-]+)", cmd)
            tgt = (m[-1].rstrip("/") if m else "")
            if tgt in KNOWN:
                self.log.append({"cmd":cmd,"matched":KNOWN[tgt],"status":"ok"})
                return open(os.path.join(self.d, KNOWN[tgt]), errors="replace").read()
            # An uncaptured path must say so. Returning a stock listing for any dkms-ish path
            # let a model descend .../nct6687d/nct6687d/nct6687d/ forever -- 11 wasted turns.
            self.log.append({"cmd":cmd,"matched":None,"status":"enoent"})
            return f"ls: cannot access '{tgt}': No such file or directory\n"
        if re.match(r"\s*(sudo\s+)?uname", cmd):
            self.log.append({"cmd":cmd,"matched":"uname_r.txt","status":"ok"})
            return open(os.path.join(self.d,"uname_r.txt"), errors="replace").read()
        # everything else: REALLY RUN IT against the captured files
        rewritten = self._rewrite(cmd)
        ok, why = self._safe(rewritten)
        if not ok:
            self.log.append({"cmd":cmd,"matched":None,"status":"refused","why":why})
            return f"replay: refused ({why}). Read-only text commands only.\n"
        try:
            r = subprocess.run(["bash","-c",rewritten], capture_output=True, text=True,
                               timeout=20, cwd=self.tmp)
            out = (r.stdout or "") + (r.stderr or "")
            self.log.append({"cmd":cmd,"matched":"EXECUTED","status":"ok","src_state":self.src})
            return out if out.strip() else "(no output)\n"
        except subprocess.TimeoutExpired:
            self.log.append({"cmd":cmd,"matched":None,"status":"timeout"})
            return "replay: command timed out\n"

if __name__ == "__main__":
    sh = ExecReplay(sys.argv[1])
    for c in sys.argv[2:]:
        print(f"$ {c}"); print(sh.run(c)[:500])
