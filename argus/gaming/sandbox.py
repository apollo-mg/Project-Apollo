"""bwrap sandbox for the agentic gaming instrument (data/receipts/agentic-gaming/DESIGN_v0.md, revision 2).

Every agent tool runs inside: read-only /usr and the project venv (interpreter and test tools only; the repo around it is
not bound), a fresh tmpfs /tmp, empty /home, /mnt and /run, no network (--unshare-all), its own pid namespace, killed
with its parent. Only the task workspace is bound writable, at /work. Instrument files (generated copies, reference
solutions, hidden checks, canaries) live outside every bound path, so the agent cannot reach them.
"""
import os, subprocess
from pathlib import Path

VENV = Path(__file__).resolve().parents[2] / "venv_cachyos"
ENV = {"PATH": f"{VENV}/bin:/usr/bin", "HOME": "/work", "PYTHONDONTWRITEBYTECODE": "1", "LANG": "C.UTF-8",
       "PYTEST_ADDOPTS": "-p no:cacheprovider", "GIT_CONFIG_NOSYSTEM": "1"}


def bwrap_argv(ws, writable=True, extra_ro=()):
    a = ["bwrap", "--ro-bind", "/usr", "/usr", "--symlink", "usr/bin", "/bin", "--symlink", "usr/lib", "/lib",
         "--symlink", "usr/lib64", "/lib64", "--ro-bind-try", "/etc/alternatives", "/etc/alternatives",
         "--ro-bind-try", "/etc/ld.so.cache", "/etc/ld.so.cache", "--ro-bind", str(VENV), str(VENV),
         "--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp", "--unshare-all", "--die-with-parent", "--new-session",
         "--clearenv"]
    for k, v in ENV.items():
        a += ["--setenv", k, v]
    for src, dst in extra_ro:
        a += ["--ro-bind", str(src), str(dst)]
    a += ["--bind" if writable else "--ro-bind", str(ws), "/work", "--chdir", "/work"]
    return a


def run(ws, argv, timeout=120, stdin=None, writable=True, extra_ro=()):
    """Run argv inside the sandbox; returns (returncode, stdout, stderr). A timeout returns code 124."""
    try:
        p = subprocess.run(bwrap_argv(ws, writable, extra_ro) + list(argv), input=stdin, capture_output=True,
                           text=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired as e:
        return 124, (e.stdout or b"").decode(errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or ""), "timeout"


# --- the agent's four tools, all executed inside the sandbox -------------------------------------------------------
def tool_read_file(ws, path):
    return run(ws, ["cat", "--", path])


def tool_write_file(ws, path, content):
    return run(ws, ["sh", "-c", 'mkdir -p "$(dirname -- "$1")" && cat > "$1"', "sh", path], stdin=content)


def tool_list_dir(ws, path="."):
    return run(ws, ["ls", "-la", "--", path])


def tool_run(ws, command, timeout=120):
    return run(ws, ["sh", "-c", command], timeout=timeout)
