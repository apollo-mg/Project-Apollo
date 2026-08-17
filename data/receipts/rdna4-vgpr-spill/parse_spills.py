#!/usr/bin/env python3
"""Parse -Rpass-analysis=kernel-resource-usage remarks into a spill census.

Matched to the 2026-08-14 gfx1201 baseline so before/after is apples-to-apples:
that run reported 7034 kernels analysed, 346 flash_attn_ext_vec, 98 spilling,
worst 735 VGPRs spilled, head sizes 256 / 128 / 64.

Each kernel emits a block of remarks led by `Function Name:`; the fields we need are
`VGPRs Spill:` and `SGPRs Spill:`. Head size is recovered from the mangled name where
possible -- the FA vec instantiations carry it as a template integer.
"""
import gzip, re, sys, collections

FN = re.compile(r"Function Name:\s*(\S+)")
VSP = re.compile(r"VGPRs Spill:\s*(\d+)")
SSP = re.compile(r"SGPRs Spill:\s*(\d+)")
OCC = re.compile(r"Occupancy \[waves/SIMD\]:\s*(\d+)")


def load(path):
    op = gzip.open if path.endswith(".gz") else open
    return op(path, "rt", errors="replace")


def parse(path):
    cur = None
    kernels = []
    for line in load(path):
        m = FN.search(line)
        if m:
            cur = {"name": m.group(1), "vspill": 0, "sspill": 0, "occ": None}
            kernels.append(cur)
            continue
        if cur is None:
            continue
        m = VSP.search(line)
        if m: cur["vspill"] = int(m.group(1)); continue
        m = SSP.search(line)
        if m: cur["sspill"] = int(m.group(1)); continue
        m = OCC.search(line)
        if m: cur["occ"] = int(m.group(1))
    # de-dup: the same kernel can be emitted per TU
    seen = {}
    for k in kernels:
        prev = seen.get(k["name"])
        if prev is None or k["vspill"] > prev["vspill"]:
            seen[k["name"]] = k
    return list(seen.values())


def headsize(name):
    # FA vec instantiations encode head size as a template int in the mangled name
    for hs in (576, 256, 192, 128, 112, 96, 80, 64, 40):
        if f"ILi{hs}E" in name:
            return hs
    return None


def report(tag, ks):
    fa = [k for k in ks if "flash_attn_ext_vec" in k["name"]]
    fa_sp = [k for k in fa if k["vspill"] > 0]
    all_sp = [k for k in ks if k["vspill"] > 0]
    print(f"=== {tag} ===")
    print(f"  kernels analysed      {len(ks)}")
    print(f"  flash_attn_ext_vec    {len(fa)}")
    print(f"  FA kernels spilling   {len(fa_sp)}")
    print(f"  worst FA VGPR spill   {max((k['vspill'] for k in fa_sp), default=0)}")
    print(f"  ALL kernels spilling  {len(all_sp)}  (worst {max((k['vspill'] for k in all_sp), default=0)})")
    by = collections.Counter(headsize(k["name"]) for k in fa_sp)
    if by:
        print("  spilling FA by head size: " +
              ", ".join(f"{h}:{n}" for h, n in sorted(by.items(), key=lambda x: -(x[0] or 0))))
    return {"fa": len(fa), "fa_sp": len(fa_sp),
            "worst": max((k["vspill"] for k in fa_sp), default=0),
            "by": dict(by), "spillers": {k["name"]: k["vspill"] for k in fa_sp}}


if __name__ == "__main__":
    a = report(sys.argv[1], parse(sys.argv[2]))
    if len(sys.argv) > 4:
        b = report(sys.argv[3], parse(sys.argv[4]))
        print("\n=== DELTA (after - before) ===")
        print(f"  FA spilling  {b['fa_sp']} -> {a['fa_sp']}   ({a['fa_sp']-b['fa_sp']:+d})")
        print(f"  worst spill  {b['worst']} -> {a['worst']}   ({a['worst']-b['worst']:+d})")
        fixed = set(b["spillers"]) - set(a["spillers"])
        new = set(a["spillers"]) - set(b["spillers"])
        print(f"  kernels FIXED (spilled before, clean now): {len(fixed)}")
        print(f"  kernels NEWLY spilling:                    {len(new)}")
        for h in sorted(set(list(a["by"]) + list(b["by"])), key=lambda x: -(x or 0)):
            print(f"    head size {h}: {b['by'].get(h,0)} -> {a['by'].get(h,0)}")
