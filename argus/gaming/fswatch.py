"""Host-side file-event watcher for the agentic gaming instrument (ctypes inotify; nothing to install).

Watches a workspace tree from OUTSIDE the agent's sandbox and records opens, reads, writes, creates, deletes and moves,
with the inode of each file, so a hard link or rename cannot hide which file was touched. New directories get watches
as they appear. A queue overflow makes the whole record invalid (fail closed): a detector that may have missed events
must not report "nothing happened".

Usage:
    w = Watcher(root); w.start()
    w.prove(sentinel_path)      # open a sentinel and wait for its event; raises if the watch is not live
    ... run the agent ...
    events = w.stop()           # list of dicts: t, kind, path, inode; raises Overflow if any were lost
"""
import ctypes, ctypes.util, os, select, struct, threading, time

IN_ACCESS, IN_MODIFY, IN_CLOSE_WRITE, IN_OPEN = 0x001, 0x002, 0x008, 0x020
IN_MOVED_FROM, IN_MOVED_TO, IN_CREATE, IN_DELETE = 0x040, 0x080, 0x100, 0x200
IN_Q_OVERFLOW, IN_ISDIR, IN_IGNORED = 0x4000, 0x40000000, 0x8000
MASK = IN_ACCESS | IN_MODIFY | IN_CLOSE_WRITE | IN_OPEN | IN_MOVED_FROM | IN_MOVED_TO | IN_CREATE | IN_DELETE
KINDS = {IN_ACCESS: "read", IN_MODIFY: "modify", IN_CLOSE_WRITE: "close_write", IN_OPEN: "open",
         IN_MOVED_FROM: "moved_from", IN_MOVED_TO: "moved_to", IN_CREATE: "create", IN_DELETE: "delete"}
_HDR = struct.Struct("iIII")
_libc = ctypes.CDLL(ctypes.util.find_library("c"), use_errno=True)


class Overflow(RuntimeError):
    """The kernel dropped events: the record is incomplete and the run must be treated as invalid."""


class Watcher:
    def __init__(self, root):
        self.root = os.path.realpath(root)
        self.fd = _libc.inotify_init1(os.O_NONBLOCK | os.O_CLOEXEC)
        if self.fd < 0:
            raise OSError(ctypes.get_errno(), "inotify_init1 failed")
        self.wd = {}            # watch descriptor -> directory path
        self.events, self.overflow = [], False
        self._stop = threading.Event(); self._thread = None

    def _add(self, d):
        wd = _libc.inotify_add_watch(self.fd, os.fsencode(d), MASK)
        if wd < 0:
            raise OSError(ctypes.get_errno(), f"inotify_add_watch failed for {d}")
        self.wd[wd] = d

    def start(self):
        for d, _, _ in os.walk(self.root):
            self._add(d)
        self._thread = threading.Thread(target=self._loop, daemon=True); self._thread.start()
        return self

    def _inode(self, p):
        try:
            return os.lstat(p).st_ino
        except OSError:
            return None

    def _loop(self):
        while not self._stop.is_set():
            r, _, _ = select.select([self.fd], [], [], 0.1)
            if not r:
                continue
            try:
                buf = os.read(self.fd, 65536)
            except BlockingIOError:
                continue
            i = 0
            while i < len(buf):
                wd, mask, _cookie, ln = _HDR.unpack_from(buf, i)
                name = buf[i + _HDR.size:i + _HDR.size + ln].rstrip(b"\0").decode(errors="replace")
                i += _HDR.size + ln
                if mask & IN_Q_OVERFLOW:
                    self.overflow = True
                    continue
                if mask & IN_IGNORED:
                    continue
                d = self.wd.get(wd, "?")
                p = os.path.join(d, name) if name else d
                if mask & IN_CREATE and mask & IN_ISDIR:
                    try:
                        for sub, _, _ in os.walk(p):
                            self._add(sub)
                    except OSError:
                        pass
                for bit, kind in KINDS.items():
                    if mask & bit:
                        self.events.append({"t": time.time(), "kind": kind, "path": os.path.relpath(p, self.root),
                                            "inode": self._inode(p), "dir": bool(mask & IN_ISDIR)})

    def prove(self, sentinel, timeout=5.0):
        """Open a sentinel inside the root and wait until its open event arrives; raise if the watch is not live."""
        with open(sentinel, "a"):
            pass
        rel = os.path.relpath(os.path.realpath(sentinel), self.root); t0 = time.time()
        while time.time() - t0 < timeout:
            if any(e["path"] == rel and e["kind"] == "open" for e in list(self.events)):
                return True
            time.sleep(0.05)
        raise RuntimeError(f"watch not live: no open event for {rel} within {timeout}s")

    def stop(self):
        time.sleep(0.3)          # let in-flight events drain
        self._stop.set(); self._thread.join(timeout=2); os.close(self.fd)
        if self.overflow:
            raise Overflow("inotify queue overflowed: events were lost")
        return self.events
