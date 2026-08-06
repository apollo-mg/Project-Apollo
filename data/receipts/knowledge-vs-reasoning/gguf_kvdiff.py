import struct, sys
U8,I8,U16,I16,U32,I32,F32,BOOL,STR,ARR,U64,I64,F64 = range(13)
_FIX={U8:("<B",1),I8:("<b",1),U16:("<H",2),I16:("<h",2),U32:("<I",4),I32:("<i",4),
      F32:("<f",4),BOOL:("<?",1),U64:("<Q",8),I64:("<q",8),F64:("<d",8)}
class R:
    def __init__(s,f): s.f=f
    def raw(s,n):
        b=s.f.read(n)
        if len(b)!=n: raise EOFError
        return b
    def fix(s,t): fmt,n=_FIX[t]; return struct.unpack(fmt,s.raw(n))[0]
    def string(s): return s.raw(s.fix(U64)).decode("utf-8","replace")
    def value(s,t):
        if t==STR: return s.string()
        if t==ARR:
            et=s.fix(U32); n=s.fix(U64)
            if et==STR:
                for _ in range(n): s.raw(s.fix(U64))
                return f"<{n} strings>"
            v=[s.value(et) for _ in range(n)]
            return v if n<=8 else f"<{n} items>"
        return s.fix(t)
def kvs(path):
    with open(path,"rb") as f:
        r=R(f); r.raw(4); r.fix(U32); r.fix(U64); n=r.fix(U64)
        d={}
        for _ in range(n):
            k=r.string(); d[k]=r.value(r.fix(U32))
        return d
a=kvs(sys.argv[1]); b=kvs(sys.argv[2])
print("ONLY IN BASE:")
for k in sorted(set(a)-set(b)): print(f"   {k} = {a[k]}")
print("ONLY IN REAP:")
for k in sorted(set(b)-set(a)): print(f"   {k} = {b[k]}")
print("DIFFERING VALUES:")
for k in sorted(set(a)&set(b)):
    if a[k]!=b[k]: print(f"   {k}\n      base = {str(a[k])[:70]}\n      reap = {str(b[k])[:70]}")
