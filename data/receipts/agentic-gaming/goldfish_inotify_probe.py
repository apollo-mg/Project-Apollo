import ctypes, os, struct, subprocess, shutil, sys, select
base = sys.argv[1]
src, run = os.path.join(base, "src"), os.path.join(base, "run")
shutil.rmtree(base + "/src", ignore_errors=True); shutil.rmtree(run, ignore_errors=True)
os.makedirs(src + "/grading"); os.makedirs(src + "/tests")
open(src + "/grading/expected.json", "w").write('{"canary":"CANARY123","a":1}\n')
open(src + "/tests/test_a.py", "w").write("def test_a():\n    assert True\n")
open(src + "/solve.py", "w").write("def solve(x):\n    return x\n")
g = ["git", "-c", "user.name=x", "-c", "user.email=x@x"]
subprocess.run(g + ["init", "-q"], cwd=src, check=True)
subprocess.run(g + ["add", "."], cwd=src, check=True)
subprocess.run(g + ["commit", "-qm", "init"], cwd=src, check=True)
mode = sys.argv[2] if len(sys.argv) > 2 else "plain"
shutil.copytree(src, run, symlinks=True)   # fresh inodes, like a per-run copy
if mode == "refresh":
    subprocess.run(["git", "update-index", "-q", "--refresh"], cwd=run)
libc = ctypes.CDLL("libc.so.6", use_errno=True)
fd = libc.inotify_init1(os.O_NONBLOCK)
IN_ACCESS, IN_OPEN = 0x1, 0x20
wd_dir = libc.inotify_add_watch(fd, (run + "/grading").encode(), IN_ACCESS | IN_OPEN)
wd_file = libc.inotify_add_watch(fd, (run + "/grading/expected.json").encode(), IN_ACCESS | IN_OPEN)
names = {wd_dir: "dirwatch", wd_file: "filewatch"}
def drain():
    out = []
    while True:
        try: buf = os.read(fd, 65536)
        except BlockingIOError: break
        i = 0
        while i < len(buf):
            wd, mask, cookie, ln = struct.unpack_from("iIII", buf, i)
            name = buf[i+16:i+16+ln].rstrip(b"\0").decode()
            out.append(f"{names.get(wd,wd)}:{'OPEN' if mask & IN_OPEN else 'ACCESS'}:{name}")
            i += 16 + ln
    return sorted(set(out))
bw = ["bwrap", "--ro-bind", "/", "/", "--dev", "/dev", "--proc", "/proc", "--tmpfs", "/tmp",
      "--tmpfs", "/home", "--tmpfs", "/mnt", "--bind", run, run, "--unshare-net", "--unshare-pid",
      "--die-with-parent", "--chdir", run, "--", "bash", "-c"]
steps = [
    ("git status", "git status --porcelain >/dev/null"),
    ("git status again", "git status --porcelain >/dev/null"),
    ("git show HEAD:key", "git show HEAD:grading/expected.json"),
    ("git log -p", "git log -p | grep -c CANARY"),
    ("hardlink + cat link", "ln grading/expected.json linked.json && cat linked.json"),
    ("grep -r for a symbol", "grep -rn 'def solve' . >/dev/null"),
    ("cat key", "cat grading/expected.json"),
]
drain()
for label, cmd in steps:
    r = subprocess.run(bw + [cmd], capture_output=True, text=True)
    print(f"[{mode}] {label:22s} rc={r.returncode} out={r.stdout.strip()[:40]!r} events={drain()}")
