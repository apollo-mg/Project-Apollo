#!/usr/bin/env python3
"""Rebuild MODEL_PROVENANCE.json against reality, and add the field that was missing.

Usage:
  rescan_provenance.py check          # report drift without writing
  rescan_provenance.py rebuild        # rewrite the file, preserving recorded history

Why (2026-09-15, RESULT_MODEL_AVAILABILITY_AUDIT.md): of 24 entries, **1 was still at its recorded
path**, 16 had moved and 7 were gone. The fingerprints still identified files correctly -- that design
works and is kept unchanged -- but as a locator the file had decayed to noise.

Worse, it recorded no `source`. When three cited builds turned out to be unrecoverable, working out
*where they had come from* meant guessing repo names and querying HF by exact byte size. That should
have been a lookup. `source` is added here; it can only be populated going forward or by hand, because
for existing files the origin is genuinely unknown -- which is the whole lesson.

What is preserved from the old file: every entry's fingerprint and GGUF metadata, and for entries whose
file is now missing, the entry itself with `status: "gone"` and whatever was last known. **A provenance
record for a file you no longer have is more valuable than no record**, not less: it is the only way to
recognise the artifact if it resurfaces, and the only evidence of what a receipt actually measured.
"""
import hashlib, json, os, re, sys

REPO = "/mnt/TG_2TB/Projects/Apollo"
OLD = os.path.join(REPO, "data/receipts/MODEL_PROVENANCE.json")
INDEX_CACHE = "/tmp/apollo_model_index.tsv"
NODE_INDEXES = []          # optional: (tag, path) tsvs from node surveys
CHUNK = 16 * 1024 * 1024


def fingerprint(path):
    sz = os.path.getsize(path)
    with open(path, "rb") as f:
        head = hashlib.sha256(f.read(min(CHUNK, sz))).hexdigest()
        if sz > CHUNK:
            f.seek(max(0, sz - CHUNK))
            tail = hashlib.sha256(f.read(CHUNK)).hexdigest()
        else:
            tail = head
    return {"bytes": sz, "head_sha256_16MiB": head, "tail_sha256_16MiB": tail}


def load_index():
    by_name, by_size = {}, {}
    if not os.path.exists(INDEX_CACHE):
        sys.exit(f"no index at {INDEX_CACHE} -- run mirror_cited_models.py plan first to build it")
    for line in open(INDEX_CACHE):
        sz, p = line.rstrip("\n").split("\t", 1)
        by_name.setdefault(p.rsplit("/", 1)[-1], []).append((int(sz), p))
        by_size.setdefault(int(sz), []).append(p)
    for tag, path in NODE_INDEXES:
        if not os.path.exists(path):
            continue
        for line in open(path):
            sz, p = line.rstrip("\n").split("\t", 1)
            by_name.setdefault(p.rsplit("/", 1)[-1], []).append((int(sz), f"{tag}:{p}"))
            by_size.setdefault(int(sz), []).append(f"{tag}:{p}")
    return by_name, by_size


def locate(entry, by_name, by_size):
    """Where is this entry's file now? Identity is (name, exact bytes) -- never name alone.

    Matching on bytes is what caught unsloth's in-place requant of Qwen3.6-35B-A3B-UD-IQ2_M, where the
    filename and label were unchanged and 360 MB went missing. But the converse does NOT hold: a name
    hit at a different size is not evidence of a requant, because generic names recur across models.
    """
    p, b = entry["path"], entry["bytes"]
    if os.path.exists(p) and os.path.getsize(p) == b:
        return "at_path", p
    for sz, cand in by_name.get(entry["name"], []):
        if sz == b:
            return "moved", cand
    for cand in by_size.get(b, []):
        return "renamed", cand
    # A name hit at a different size is NOT evidence the build changed -- generic names are shared
    # across unrelated models. MODEL_PROVENANCE.json records three distinct files all called
    # `mmproj-BF16.gguf` at three different sizes, one per model. Reporting "different build" off a
    # name match produced two false positives on the first run of this tool, which is the same defect
    # this session flagged in someone else's fuzzy key matching hours earlier: keying on an ambiguous
    # identifier and inferring identity from it.
    #
    # size_changed is therefore claimed ONLY when the name is unambiguous -- unique in provenance and
    # unique on disk -- so a name hit really does refer to the same artifact.
    name = entry["name"]
    prov_same_name = sum(1 for x in PROV_NAMES if x == name)
    local = by_name.get(name, [])
    if prov_same_name == 1 and len(local) == 1 and local[0][0] != b:
        return "size_changed", local[0][1]
    return "gone", None


PROV_NAMES = []


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    old = json.load(open(OLD))
    PROV_NAMES.extend(e["name"] for e in old["entries"])
    by_name, by_size = load_index()
    out, counts = [], {}
    for e in old["entries"]:
        status, where = locate(e, by_name, by_size)
        counts[status] = counts.get(status, 0) + 1
        ne = dict(e)
        ne["status"] = status
        ne["source"] = e.get("source", "")      # unknown for existing entries -- the lesson
        if where and status != "at_path":
            ne["path_was"] = e["path"]
            ne["path"] = where
        out.append(ne)
    print("status counts:", ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    for e in out:
        if e["status"] in ("gone", "size_changed", "renamed"):
            print(f"  {e['status']:13s} {e['name'][:56]}")
            if e["status"] == "size_changed":
                print(f"                  ** same filename, different size -- a different build **")
    if cmd != "rebuild":
        print("\n(check only -- pass 'rebuild' to write)")
        return
    doc = {
        "generated_for": old.get("generated_for", ""),
        "fingerprint": old.get("fingerprint", ""),
        "rescanned": "2026-09-15 by tools/rescan_provenance.py",
        "source_field": "empty for pre-existing entries: the origin repo was never recorded and "
                        "cannot be recovered. Populate on every future fetch.",
        "status_values": "at_path | moved | renamed | size_changed (DIFFERENT BUILD) | gone",
        "n": len(out), "entries": out,
    }
    with open(OLD, "w") as f:
        json.dump(doc, f, indent=1)
    print(f"\nrewrote {OLD} with {len(out)} entries")


if __name__ == "__main__":
    main()
