#!/usr/bin/env python3
"""Make every receipt-cited model exist on two volumes, with a fingerprint recorded.

Usage:
  mirror_cited_models.py plan                 # what would be copied, and where
  mirror_cited_models.py run [--limit GiB]    # copy + verify, resumable
  mirror_cited_models.py verify               # re-check fingerprints of the mirror set

Why this exists (2026-09-15, RESULT_MODEL_AVAILABILITY_AUDIT.md): 24 of 29 heavily-cited models had
exactly one copy, and three others were already gone -- one re-quantized upstream under the SAME
filename, one quant pruned from its repo, one repo gated. Nothing about that required a platform
policy change; it is ordinary repo churn, and it cost three published receipts their reproducibility.

Two rules the audit earned the hard way:

  * **Fingerprint everything.** unsloth re-quantized Qwen3.6-35B-A3B-UD-IQ2_M in place: same filename,
    same label, 360 MB smaller. A mirror without fingerprints would silently hold the wrong build and
    report success. Fingerprint = sha256 of the first and last 16 MiB plus the exact byte count, which
    is the scheme MODEL_PROVENANCE.json already uses and is ~1000x cheaper than hashing 20 GB.
  * **Copy, verify at the destination, THEN record.** Never trust a transfer's exit code as evidence
    the bytes arrived.

Direction is chosen per file: a model whose only copy is on the NAS is mirrored to TG_2TB, and
everything else is mirrored to the NAS. The point is two volumes, not a particular one.
"""
import hashlib, json, os, re, shutil, subprocess, sys

REPO = "/mnt/TG_2TB/Projects/Apollo"
NAS = "/mnt/HDD/apollo-mirror"
LOCAL = "/mnt/TG_2TB/AI/Models/_mirror"
STATE = os.path.join(REPO, "data/receipts/MODEL_MIRROR.json")
CHUNK = 16 * 1024 * 1024
MIN_CITATIONS = 13

# A second selection rule, added 2026-09-15 at Mark's request. Receipt citations protect what the
# published work depends on; this protects what is hardest to RE-ACQUIRE. Decensored/abliterated
# derivatives are the category most exposed to a repository going away, and the audit has a live
# example: ornith-ai/Ornith-1.0-35B-A3B now returns an auth error, so its IQ2_M is simply gone.
# These are community fine-tunes, often from single uploaders, frequently not mirrored anywhere.
KEEP_PATTERN = re.compile(r"abliterat|heretic|uncen|unheretic|decensor", re.I)


def fingerprint(path):
    """sha256 of first and last 16 MiB + exact size. Cheap, and sufficient to catch a requant."""
    sz = os.path.getsize(path)
    with open(path, "rb") as f:
        head = hashlib.sha256(f.read(min(CHUNK, sz))).hexdigest()
        if sz > CHUNK:
            f.seek(max(0, sz - CHUNK))
            tail = hashlib.sha256(f.read(CHUNK)).hexdigest()
        else:
            tail = head
    return {"bytes": sz, "head_sha256_16MiB": head, "tail_sha256_16MiB": tail}


def citations():
    out = subprocess.run(
        ["bash", "-c", r"grep -rhoE '[A-Za-z0-9_.-]+\.(gguf|safetensors)' data/receipts/ "
                       r"| sed 's/-0000[0-9]-of-0000[0-9]//' | sort | uniq -c"],
        cwd=REPO, capture_output=True, text=True).stdout
    c = {}
    for line in out.splitlines():
        p = line.split()
        if len(p) == 2 and not p[1][:2].isdigit():
            c[p[1]] = int(p[0])
    return c


def volume(p):
    if p.startswith("/mnt/HDD"):
        return "NAS"
    if "Games" in p:
        return "Games"
    if p.startswith("/mnt/TG_2TB"):
        return "TG_2TB"
    return "home"


INDEX_CACHE = "/tmp/apollo_model_index.tsv"


def index(max_age_s=3600):
    """Every model file on locally mounted storage. Nodes are surveyed separately -- a copy that
    exists only on a compute node does NOT count as redundancy: nodes get wiped and reinstalled.

    Cached: walking /mnt/HDD over CIFS takes minutes and every subcommand needs the same index.
    Delete INDEX_CACHE or pass max_age_s=0 to force a rescan after moving files around.
    """
    import time
    if max_age_s and os.path.exists(INDEX_CACHE) and time.time() - os.path.getmtime(INDEX_CACHE) < max_age_s:
        found = {}
        for line in open(INDEX_CACHE):
            sz, p = line.rstrip("\n").split("\t", 1)
            found.setdefault(p.rsplit("/", 1)[-1], []).append((int(sz), p))
        return found
    found = {}
    roots = ["/mnt/TG_2TB/AI/Models", "/home/mark", "/run/media/mark/Games 2TB", "/mnt/HDD"]
    for r in roots:
        if not os.path.isdir(r):
            continue
        for dirpath, _, files in os.walk(r):
            if "_mirror" in dirpath or "apollo-mirror" in dirpath:
                continue
            for fn in files:
                if fn.endswith((".gguf", ".safetensors")):
                    p = os.path.join(dirpath, fn)
                    try:
                        found.setdefault(fn, []).append((os.path.getsize(p), p))
                    except OSError:
                        pass
    with open(INDEX_CACHE, "w") as f:
        for fn, lst in found.items():
            for sz, p in lst:
                f.write(f"{sz}\t{p}\n")
    return found


def plan():
    cites, have = citations(), index()
    jobs = []
    candidates = {n: c for n, c in cites.items() if c >= MIN_CITATIONS}
    # plus every single-copy file matching KEEP_PATTERN, whether or not a receipt cites it
    for name in have:
        if KEEP_PATTERN.search(name):
            candidates.setdefault(name, 0)
    for name, n in sorted(candidates.items(), key=lambda x: -x[1]):
        if name not in have:
            continue
        copies = have[name]
        vols = {volume(p) for _, p in copies}
        if len(vols) > 1:
            continue                      # already redundant
        src_sz, src = max(copies)          # largest if duplicates within one volume
        dest_root = LOCAL if volume(src) == "NAS" else NAS
        jobs.append({"name": name, "citations": n, "bytes": src_sz, "src": src,
                     "dest": os.path.join(dest_root, name), "from": volume(src),
                     "to": "TG_2TB" if dest_root == LOCAL else "NAS"})
    return jobs


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "plan"
    jobs = plan()
    done = json.load(open(STATE))["entries"] if os.path.exists(STATE) else []
    done_names = {e["name"] for e in done if e.get("verified")}

    if cmd == "plan":
        tot = sum(j["bytes"] for j in jobs if j["name"] not in done_names)
        print(f"{len(jobs)} single-copy cited models; {len(done_names)} already mirrored")
        print(f"to copy: {tot/2**30:.1f} GiB\n")
        print(f"| cites | model | {'from':>7} -> {'to':<7} | GiB |")
        print("|---:|---|---|---:|")
        for j in jobs:
            mark = " ✓" if j["name"] in done_names else ""
            print(f"| {j['citations']} | `{j['name'][:52]}`{mark} | {j['from']:>7} → {j['to']:<7} "
                  f"| {j['bytes']/2**30:.1f} |")
        return

    if cmd == "verify":
        bad = 0
        for e in done:
            if not os.path.exists(e["dest"]):
                print(f"  MISSING {e['dest']}"); bad += 1; continue
            fp = fingerprint(e["dest"])
            if fp != {k: e[k] for k in fp}:
                print(f"  ** FINGERPRINT MISMATCH ** {e['dest']}"); bad += 1
        print(f"verified {len(done)} entries, {bad} problem(s)")
        return

    limit = float(sys.argv[sys.argv.index("--limit") + 1]) * 2**30 if "--limit" in sys.argv else None
    copied = 0
    for j in jobs:
        if j["name"] in done_names:
            continue
        if limit and copied + j["bytes"] > limit:
            print(f"  limit reached, stopping before {j['name']}"); break
        os.makedirs(os.path.dirname(j["dest"]), exist_ok=True)
        print(f"=== {j['name']}  {j['bytes']/2**30:.1f} GiB  {j['from']} → {j['to']}", flush=True)
        src_fp = fingerprint(j["src"])
        tmp = j["dest"] + ".partial"
        try:
            shutil.copyfile(j["src"], tmp)
        except OSError as e:
            print(f"  COPY FAILED: {e}"); continue
        dst_fp = fingerprint(tmp)
        if dst_fp != src_fp:
            print(f"  ** FINGERPRINT MISMATCH after copy -- leaving .partial, not recording **")
            continue
        os.replace(tmp, j["dest"])
        entry = {"name": j["name"], "citations": j["citations"], "src": j["src"],
                 "dest": j["dest"], "verified": True, **src_fp}
        done = [e for e in done if e["name"] != j["name"]] + [entry]
        os.makedirs(os.path.dirname(STATE), exist_ok=True)
        with open(STATE, "w") as f:
            json.dump({"generated": "tools/mirror_cited_models.py",
                       "fingerprint": "sha256 of first and last 16 MiB + exact byte size",
                       "note": "a copy on a compute node does not count as redundancy",
                       "n": len(done), "entries": sorted(done, key=lambda e: -e["citations"])}, f, indent=1)
        copied += j["bytes"]
        print(f"  verified {src_fp['head_sha256_16MiB'][:16]}… → recorded", flush=True)
    print(f"\ncopied {copied/2**30:.1f} GiB this run")


if __name__ == "__main__":
    main()
