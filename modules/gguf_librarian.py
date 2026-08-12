#!/usr/bin/env python3
"""Name and shelve GGUFs by what they ACTUALLY contain, not what the file says.

Why this exists: the filename quant label is not a spec. Measured on this fleet --
`UD-Q8_K_XL` whose experts are 100% MXFP4, `Q4_K_M` whose experts are a Q4_K/Q6_K
mix, `IQ2_M` whose experts are IQ2_XXS/IQ3_XXS/IQ4_XS/IQ2_S. The label describes
(roughly) the dense tensors and says nothing about the experts, which is where the
behaviour lives.

The two expert properties that decided real outcomes in `data/receipts/rdna4-moe-cache`:

  * expert TYPE   -- decides cache eligibility per backend. CUDA/HIP covers 23
                     types; Vulkan and Metal cover exactly 4 (Q8_0/Q4_0/Q4_K/Q6_K)
                     and neither includes Q5_K or any IQ type.
  * per-expert SIZE -- decides the pre-Ampere floor. 840 KiB silently blocked every
                     P100 run and reported "no cacheable expert tensors found",
                     naming the wrong thing; 3200 KiB clears it stock.

Neither is recoverable from the filename. Both are exact functions of the header.

DELIBERATELY NOT AN LLM TASK. Extracting these is deterministic and correct 100%
of the time; a model in this loop can only subtract reliability. The fuzzy part --
reconciling `Qwopus3.6-35B-A3B-v1` with `Qwen3.6-35B-A3B` as one family, or picking
a taxonomy -- is where judgement belongs, and it stays advisory: this tool proposes,
a human approves, and nothing writes without an explicit --apply.

Safety: 250 distinct .gguf path strings live in this repo, 215 of them inside
`data/receipts/`. A rename invalidates the provenance of the published corpus, so
the default apply mode is SYMLINK -- originals stay put, truthful names point at
them. `--apply move` exists but must be asked for.

Usage:
  gguf_librarian.py scan   [roots...]              # census + liar report (default)
  gguf_librarian.py plan   [roots...]              # proposed shelf layout
  gguf_librarian.py apply  --link DEST [roots...]  # build the shelf as symlinks
  gguf_librarian.py apply  --move DEST [roots...]  # actually relocate (asks first)
  --manifest PATH                                  # write the census as JSON

Companion to `data/receipts/model_manifest.py`, which records provenance
(fingerprint + source) for cited models. This one describes contents for all of them.
"""
import argparse, collections, json, os, re, struct, sys

# (block elements, bytes per block). Exact -- this is what makes per-expert size
# exact rather than a bits-per-weight estimate.
TRAITS = {
    0: ("F32", 1, 4), 1: ("F16", 1, 2), 2: ("Q4_0", 32, 18), 3: ("Q4_1", 32, 20),
    6: ("Q5_0", 32, 22), 7: ("Q5_1", 32, 24), 8: ("Q8_0", 32, 34), 9: ("Q8_1", 32, 36),
    10: ("Q2_K", 256, 84), 11: ("Q3_K", 256, 110), 12: ("Q4_K", 256, 144),
    13: ("Q5_K", 256, 176), 14: ("Q6_K", 256, 210), 15: ("Q8_K", 256, 292),
    16: ("IQ2_XXS", 256, 66), 17: ("IQ2_XS", 256, 74), 18: ("IQ3_XXS", 256, 98),
    19: ("IQ1_S", 256, 50), 20: ("IQ4_NL", 32, 18), 21: ("IQ3_S", 256, 110),
    22: ("IQ2_S", 256, 82), 23: ("IQ4_XS", 256, 136), 24: ("I8", 1, 1),
    25: ("I16", 1, 2), 26: ("I32", 1, 4), 27: ("I64", 1, 8), 28: ("F64", 1, 8),
    29: ("IQ1_M", 256, 56), 30: ("BF16", 1, 2), 31: ("TQ1_0", 256, 54),
    32: ("TQ2_0", 256, 66), 39: ("MXFP4", 32, 17),
}

# Backend cache coverage, read out of the providers in the moe-cache branch.
# Verified by enumerating every GGML_TYPE reference in each provider source.
VULKAN_METAL_CACHEABLE = {"Q8_0", "Q4_0", "Q4_K", "Q6_K"}
PRE_AMPERE_MIN_EXPERT = 1024 * 1024   # cc < 800 floor
AMPERE_MIN_EXPERT = 512 * 1024        # cc >= 800 floor

COMPANION = re.compile(r"(mmproj|^mtp-|imatrix|draft)", re.I)
# Quant label as advertised in the filename, longest-match first so UD-Q8_K_XL
# does not get read as Q8_K.
LABEL = re.compile(
    r"(UD-[A-Z0-9_]+(?:-[A-Z]+)?|IQ\d+_[A-Z]+(?:_[A-Z]+)?|Q\d+_[A-Z0-9]+(?:_[A-Z]+)?"
    r"|BF16|F16|F32|TQ\d_\d)", re.I)


def _val(f, vt):
    simple = {0: ("<B", 1), 1: ("<b", 1), 2: ("<H", 2), 3: ("<h", 2), 4: ("<I", 4),
              5: ("<i", 4), 6: ("<f", 4), 7: ("<?", 1), 10: ("<Q", 8), 11: ("<q", 8),
              12: ("<d", 8)}
    if vt in simple:
        fmt, n = simple[vt]
        return struct.unpack(fmt, f.read(n))[0]
    if vt == 8:
        n = struct.unpack("<Q", f.read(8))[0]
        return f.read(n).decode("utf-8", "replace")
    if vt == 9:
        et = struct.unpack("<I", f.read(4))[0]
        n = struct.unpack("<Q", f.read(8))[0]
        return [_val(f, et) for _ in range(n)]
    raise ValueError(f"unknown gguf value type {vt}")


def read_gguf(path):
    """Header + full tensor table. Never touches tensor DATA, so this is a few
    MiB of read regardless of whether the file is 4 GiB or 400."""
    out = {"path": path, "bytes": os.path.getsize(path)}
    with open(path, "rb") as f:
        if f.read(4) != b"GGUF":
            return {**out, "error": "not a GGUF"}
        out["gguf_version"] = struct.unpack("<I", f.read(4))[0]
        n_tensors, n_kv = struct.unpack("<QQ", f.read(16))
        kv = {}
        for _ in range(n_kv):
            klen = struct.unpack("<Q", f.read(8))[0]
            key = f.read(klen).decode("utf-8", "replace")
            vt = struct.unpack("<I", f.read(4))[0]
            v = _val(f, vt)
            if not isinstance(v, list) or len(v) <= 8:
                kv[key] = v
        arch = kv.get("general.architecture", "?")
        out.update(
            arch=arch,
            name=kv.get("general.name"),
            n_tensors=n_tensors,
            block_count=kv.get(f"{arch}.block_count"),
            n_embd=kv.get(f"{arch}.embedding_length"),
            n_expert=kv.get(f"{arch}.expert_count"),
            n_expert_used=kv.get(f"{arch}.expert_used_count"),
            expert_ffn=kv.get(f"{arch}.expert_feed_forward_length"),
            split_no=kv.get("split.no"), split_count=kv.get("split.count"),
        )
        exp_types, exp_bytes, other = collections.Counter(), {}, collections.Counter()
        for _ in range(n_tensors):
            nlen = struct.unpack("<Q", f.read(8))[0]
            tname = f.read(nlen).decode("utf-8", "replace")
            nd = struct.unpack("<I", f.read(4))[0]
            ne = [struct.unpack("<Q", f.read(8))[0] for _ in range(nd)]
            ty = struct.unpack("<I", f.read(4))[0]
            struct.unpack("<Q", f.read(8))  # offset
            tn, blk, tsz = TRAITS.get(ty, (f"type{ty}", 0, 0))
            if ("_exps" in tname or "_chexps" in tname) and nd == 3 and blk:
                exp_types[tn] += 1
                # bytes for ONE expert = rows * row_size; this is the value the
                # eligibility floor is compared against.
                exp_bytes[tn] = (ne[0] // blk) * tsz * ne[1]
            else:
                other[tn] += 1
        out["expert_types"] = dict(exp_types)
        out["expert_bytes"] = exp_bytes
        out["other_types"] = dict(other)
    return out


def verdict(m):
    """What the file can actually do, and where the filename lies."""
    v = {}
    et = set(m.get("expert_types") or {})
    if et:
        v["moe"] = True
        v["cuda_hip_cacheable"] = True          # CUDA covers all 23 quant types
        v["vulkan_metal_cacheable"] = et <= VULKAN_METAL_CACHEABLE
        # A mixed-type model has a per-expert size PER TYPE. The floor is applied
        # per tensor, so the smallest is what gates -- report that, not the max,
        # or a model reads as eligible while most of its experts are excluded.
        sizes = list(m.get("expert_bytes", {}).values()) or [0]
        v["per_expert_bytes"] = min(sizes)
        v["per_expert_bytes_max"] = max(sizes)
        v["pascal_ok_stock"] = min(sizes) >= PRE_AMPERE_MIN_EXPERT
        v["pascal_ok_partial"] = max(sizes) >= PRE_AMPERE_MIN_EXPERT
        v["ampere_ok_stock"] = min(sizes) >= AMPERE_MIN_EXPERT
    else:
        v["moe"] = False
    label = LABEL.search(os.path.basename(m["path"]))
    v["label"] = label.group(1).upper() if label else None
    if et and v["label"]:
        base = v["label"].replace("UD-", "").split("_XL")[0]
        # "lying" = the advertised label names a type that is not on ANY expert
        v["label_matches_experts"] = any(t.upper().startswith(base[:4]) for t in et)
    return v


def shelf(m, v):
    """Proposed nested location. Folder tree carries the truth; the original stem
    is preserved because finetune lineage is real information the header lacks."""
    arch = m.get("arch") or "unknown"
    # Projectors/draft heads are not models; they belong beside one, not filed by
    # dimensions they do not carry. A naive sweep shelves them under "NoneL-Noned".
    if m.get("companion"):
        return os.path.join(arch, "_companions")

    def part(label, val):
        return f"{val}{label}" if val is not None else f"?{label}"

    if v["moe"]:
        shape = "-".join(filter(None, [
            part("x", m.get("n_expert")).replace("x", "") + "exp",
            f"{m['n_expert_used']}used" if m.get("n_expert_used") else None,
            f"ffn{m['expert_ffn']}" if m.get("expert_ffn") else None]))
        types = "+".join(sorted(m["expert_types"]))
        lo, hi = v["per_expert_bytes"] // 1024, v["per_expert_bytes_max"] // 1024
        kib = f"{lo}KiB" if lo == hi else f"{lo}-{hi}KiB"
        profile = f"exp-{types}-{kib}"
    else:
        shape = f"{part('L', m.get('block_count'))}-{part('d', m.get('n_embd'))}"
        profile = "dense"
    return os.path.join(arch, shape, profile)


def scan(roots):
    seen, out = set(), []
    for r in roots:
        for dp, _, fns in os.walk(r):
            for fn in sorted(fns):
                if not fn.endswith(".gguf"):
                    continue
                p = os.path.join(dp, fn)
                rp = os.path.realpath(p)
                if rp in seen:
                    continue
                seen.add(rp)
                try:
                    m = read_gguf(p)
                except Exception as e:
                    m = {"path": p, "bytes": os.path.getsize(p),
                         "error": f"{type(e).__name__}: {e}"}
                m["companion"] = bool(COMPANION.search(fn))
                out.append(m)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=["scan", "plan", "apply"], nargs="?", default="scan")
    ap.add_argument("roots", nargs="*", default=["/mnt/TG_2TB/AI/Models"])
    ap.add_argument("--manifest")
    ap.add_argument("--link", metavar="DEST", help="build the shelf as symlinks")
    ap.add_argument("--move", metavar="DEST", help="RELOCATE files (destructive)")
    a = ap.parse_args()

    models = scan(a.roots)
    ok = [m for m in models if "error" not in m]
    moe = [m for m in ok if m.get("expert_types")]
    print(f"scanned {len(models)} GGUF   parsed {len(ok)}   MoE {len(moe)}   "
          f"{sum(m['bytes'] for m in models)/2**40:.2f} TiB\n")

    liars, unlabelled, mixed, blocked = [], [], [], []
    for m in ok:
        v = verdict(m)
        m["_v"] = v
        if v["moe"]:
            if v["label"] is None:
                unlabelled.append((m, v))
            elif v.get("label_matches_experts") is False:
                liars.append((m, v))
            if len(m["expert_types"]) > 1:
                mixed.append((m, v))
            if not v["vulkan_metal_cacheable"] or not v["pascal_ok_stock"]:
                blocked.append((m, v))

    print(f"=== label vs experts ({len(moe)} MoE) ===")
    print(f"  {len(mixed):>3} carry MORE THAN ONE expert type — no single label can describe them")
    print(f"  {len(liars):>3} name a type that is on no expert at all")
    print(f"  {len(unlabelled):>3} state no quant in the filename at all")
    for m, v in liars[:10]:
        print(f"    LIES      {os.path.basename(m['path'])[:52]:<52} says {v['label']:<10} "
              f"experts {'+'.join(sorted(m['expert_types']))}")
    for m, v in mixed[:10]:
        print(f"    MIXED     {os.path.basename(m['path'])[:52]:<52} "
              f"{'+'.join(sorted(m['expert_types']))}")
    if blocked:
        print(f"\n=== MoE cache limits ({len(blocked)}) ===")
        for m, v in blocked[:20]:
            why = []
            if not v["vulkan_metal_cacheable"]:
                why.append("no Vulkan/Metal kernel")
            if not v["pascal_ok_stock"]:
                why.append(f"under pre-Ampere floor ({v['per_expert_bytes']//1024} KiB)")
            print(f"  {os.path.basename(m['path'])[:56]:<56} {'; '.join(why)}")

    if a.mode in ("plan", "apply"):
        print("\n=== proposed shelf ===")
        tree = collections.defaultdict(list)
        for m in ok:
            tree[shelf(m, m["_v"])].append(m)
        for d in sorted(tree):
            print(f"  {d}/   ({len(tree[d])})")
            for m in tree[d][:3]:
                print(f"      {os.path.basename(m['path'])[:66]}")
            if len(tree[d]) > 3:
                print(f"      ... +{len(tree[d])-3} more")

    if a.mode == "apply":
        dest, move = (a.move, True) if a.move else (a.link, False)
        if not dest:
            sys.exit("apply needs --link DEST or --move DEST")
        if move:
            sys.exit("--move is destructive and 215 receipt references name these "
                     "paths; re-run with --link, or remove this guard deliberately.")
        n = 0
        for m in ok:
            d = os.path.join(dest, shelf(m, m["_v"]))
            os.makedirs(d, exist_ok=True)
            dst = os.path.join(d, os.path.basename(m["path"]))
            if not os.path.lexists(dst):
                os.symlink(os.path.realpath(m["path"]), dst)
                n += 1
        print(f"\nlinked {n} into {dest}")

    if a.manifest:
        for m in models:
            m.pop("_v", None)
        json.dump({"n": len(models), "roots": a.roots, "entries": models},
                  open(a.manifest, "w"), indent=1, default=str)
        print(f"\nmanifest -> {a.manifest}")


if __name__ == "__main__":
    main()
