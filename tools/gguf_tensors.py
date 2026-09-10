#!/usr/bin/env python3
"""Minimal GGUF tensor lister. Deliberately does NOT use gguf-py: that package is broken on
this branch (missing MODEL_ARCH.QWEN4EXP + 17 MODEL_TENSOR members), and a header parser has
no opinion about architectures anyway."""
import struct, sys, glob, re, collections

TSZ = {0:(1,32),1:(2,32),8:(1,32)}  # only need block sizes for a few; we use n_bytes from dims+type table
# (type, block_size, type_size)
GT = {0:("F32",1,4),1:("F16",1,2),2:("Q4_0",32,18),3:("Q4_1",32,20),6:("Q5_0",32,22),7:("Q5_1",32,24),
      8:("Q8_0",32,34),9:("Q8_1",32,36),10:("Q2_K",256,84),11:("Q3_K",256,110),12:("Q4_K",256,144),
      13:("Q5_K",256,176),14:("Q6_K",256,210),15:("Q8_K",256,292),16:("IQ2_XXS",256,66),
      17:("IQ2_XS",256,74),18:("IQ3_XXS",256,98),19:("IQ1_S",256,50),20:("IQ4_NL",32,18),
      21:("IQ3_S",256,110),22:("IQ2_S",256,82),23:("IQ4_XS",256,136),24:("I8",1,1),25:("I16",1,2),
      26:("I32",1,4),27:("I64",1,8),28:("F64",1,8),29:("IQ1_M",256,56),30:("BF16",1,2)}

def rd(f, fmt): 
    n=struct.calcsize(fmt); return struct.unpack(fmt, f.read(n))
def rstr(f):
    (n,)=rd(f,"<Q"); return f.read(n).decode("utf-8",errors="replace")
def skip_val(f, t):
    if t in (0,1): f.read(1)
    elif t in (2,3): f.read(2)
    elif t in (4,5,6): f.read(4)
    elif t==7: f.read(1)
    elif t==8: rstr(f)
    elif t in (10,11,12): f.read(8)
    elif t==9:
        (et,), (n,) = rd(f,"<I"), rd(f,"<Q")
        for _ in range(n): skip_val(f, et)
    else: raise ValueError(f"unknown metadata type {t}")

rows=[]
for path in sorted(glob.glob(sys.argv[1])):
    with open(path,"rb") as f:
        magic=f.read(4)
        if magic!=b"GGUF": print(f"skip {path}: not GGUF"); continue
        (ver,)=rd(f,"<I"); (ntens,)=rd(f,"<Q"); (nkv,)=rd(f,"<Q")
        for _ in range(nkv):
            rstr(f); (t,)=rd(f,"<I"); skip_val(f,t)
        for _ in range(ntens):
            name=rstr(f); (nd,)=rd(f,"<I")
            dims=[rd(f,"<Q")[0] for _ in range(nd)]
            (tt,)=rd(f,"<I"); rd(f,"<Q")
            nm,bs,ts = GT.get(tt,(f"T{tt}",1,4))
            nel=1
            for d in dims: nel*=d
            rows.append((name, nel*ts//bs, nm, dims))
print(f"  {len(rows)} tensors, {sum(r[1] for r in rows)/1024**3:.1f} GiB total\n")
fam=collections.Counter(); cnt=collections.Counter(); types=collections.Counter()
for name,b,t,d in rows:
    k=re.sub(r"\.\d+\.", ".N.", name); k=re.sub(r"^blk\.N\.","blk.N.",k)
    fam[k]+=b; cnt[k]+=1; types[t]+=b
print("  === by tensor family ===")
for k,v in fam.most_common(22):
    print(f"    {v/1024**3:8.2f} GiB  x{cnt[k]:<5} {k}")
print("\n  === by quant type ===")
for k,v in types.most_common(8):
    print(f"    {v/1024**3:8.2f} GiB  {k}")
