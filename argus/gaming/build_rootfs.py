#!/usr/bin/env python3
"""Build the agentic gaming sandbox's fixed root filesystem (RESULT_CALIBRATION_v1.md, Mark's decision 2).

The calibration's sandbox bound the host's whole /usr read-only: a searching agent wandered into the host's installed
applications, and nothing about the environment was fixed. This copies ONLY what the tasks need -- a shell and core
utilities, git, make, Python's standard library and pytest -- with every shared library they load (an ldd closure), into
one directory with fixed modification times, and writes a manifest of every file's sha256. The sandbox then binds this
directory's usr/ as /usr instead of the host's. Nothing is downloaded; the copy is a snapshot of this machine.

Usage: build_rootfs.py DEST [--manifest PATH]   (DEST must not exist)
"""
import argparse, hashlib, json, os, re, shutil, subprocess, sys
from pathlib import Path

FIXED = 1_700_000_000
VENV_SP = Path(__file__).resolve().parents[2] / "venv_cachyos" / "lib" / "python3.14" / "site-packages"
TOOLS = ("bash sh ls cat head tail grep egrep fgrep sed awk gawk find xargs wc sort uniq diff cmp tr cut tee env echo printf true "
         "false test [ mkdir rmdir rm cp mv ln touch chmod basename dirname realpath readlink pwd date sleep stat du nl seq expr "
         "timeout od xxd hexdump md5sum sha256sum python3 python3.14 git make").split()
PY_SKIP = re.compile(r"/(test|tests|idlelib|tkinter|turtledemo|ensurepip|lib2to3|site-packages|__pycache__)(/|$)")
PYTEST = ("pytest", "_pytest", "pluggy", "iniconfig", "packaging", "py.py", "pygments")


def ldd(path):
    out = subprocess.run(["ldd", str(path)], capture_output=True, text=True).stdout
    return {m.group(1) for m in re.finditer(r"(/[^\s]+\.so[^\s]*)", out)}


def copy(src, root):
    src = Path(src)
    dst = root / str(src).lstrip("/")
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.is_symlink():
        target = os.readlink(src)
        if not dst.exists() and not dst.is_symlink():
            os.symlink(target, dst)
        copy((src.parent / target).resolve(), root)       # and what it points at
    elif src.is_file() and not dst.exists():
        shutil.copy2(src, dst)


def main(a):
    root = Path(a.dest)
    if root.exists():
        sys.exit(f"{root} exists; refusing to build into it")
    root.mkdir(parents=True)
    libs = set()
    for t in TOOLS:
        p = Path("/usr/bin") / t
        if p.exists():
            copy(p, root); libs |= ldd(p.resolve())
    for p in Path("/usr/lib/git-core").rglob("*"):                      # git's helpers
        if p.is_file() or p.is_symlink():
            copy(p, root)
            if p.is_file() and os.access(p, os.X_OK):
                libs |= ldd(p)
    for p in Path("/usr/lib/python3.14").rglob("*"):                    # the standard library, without tests and caches
        if PY_SKIP.search(str(p)):
            continue
        if p.is_file() or p.is_symlink():
            copy(p, root)
            if p.suffix == ".so":
                libs |= ldd(p)
    libpy = Path("/usr/lib/libpython3.14.so.1.0")
    if libpy.exists():
        copy(libpy, root); libs |= ldd(libpy)
    sp = root / "usr/lib/python3.14/site-packages"
    sp.mkdir(parents=True, exist_ok=True)
    for name in PYTEST:                                                 # pytest and its dependencies, from the venv
        s = VENV_SP / name
        if s.is_dir():
            shutil.copytree(s, sp / name, ignore=shutil.ignore_patterns("__pycache__"))
        elif s.is_file():
            shutil.copy2(s, sp / name)
    for d in VENV_SP.glob("*.dist-info"):                               # metadata, so pytest finds its own version
        if d.name.split("-")[0].lower() in {"pytest", "pluggy", "iniconfig", "packaging", "pygments"}:
            shutil.copytree(d, sp / d.name)
    seen = set()
    while libs - seen:                                                  # the closure of shared libraries
        lib = (libs - seen).pop(); seen.add(lib)
        if Path(lib).exists():
            copy(lib, root); libs |= ldd(Path(lib).resolve())
    for f in ("/usr/lib/ld-linux-x86-64.so.2", "/usr/lib64/ld-linux-x86-64.so.2"):
        if Path(f).exists():
            copy(f, root)
    etc = root / "etc"; etc.mkdir(exist_ok=True)
    (etc / "passwd").write_text("root:x:0:0::/root:/bin/bash\nagent:x:1000:1000::/work:/bin/bash\n")
    (etc / "group").write_text("root:x:0:\nagent:x:1000:\n")
    for p in sorted(root.rglob("*"), key=lambda q: -len(q.parts)):      # fixed times, deepest first
        os.utime(p, (FIXED, FIXED), follow_symlinks=False)
    os.utime(root, (FIXED, FIXED))
    rows, total = [], 0
    for p in sorted(root.rglob("*")):
        rel = str(p.relative_to(root))
        if p.is_symlink():
            rows.append([rel, "link", os.readlink(p)])
        elif p.is_file():
            h = hashlib.sha256(p.read_bytes()).hexdigest(); total += p.stat().st_size
            rows.append([rel, "file", h])
    digest = hashlib.sha256(json.dumps(rows).encode()).hexdigest()
    man = {"root": str(root), "files": len(rows), "bytes": total, "sha256_of_manifest": digest, "entries": rows}
    Path(a.manifest or root.with_suffix(".manifest.json")).write_text(json.dumps(man, indent=0))
    print(f"rootfs {root}: {len(rows)} entries, {total / 1e6:.0f} MB, manifest sha256 {digest[:16]}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("dest"); ap.add_argument("--manifest")
    main(ap.parse_args())
