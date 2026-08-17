import struct,sys
T={0:'B',1:'b',2:'H',3:'h',4:'I',5:'i',6:'f',7:'?',10:'Q',11:'q',12:'d'}
S={0:1,1:1,2:2,3:2,4:4,5:4,6:4,7:1,10:8,11:8,12:8}
def head(p):
    try: f=open(p,'rb')
    except Exception as e: return f"open fail {e}"
    if f.read(4)!=b'GGUF': return "not gguf"
    struct.unpack('<I',f.read(4)); f.read(8)
    n,=struct.unpack('<Q',f.read(8)); got={}
    for i in range(n):
        kl,=struct.unpack('<Q',f.read(8)); k=f.read(kl).decode('utf8','replace')
        t,=struct.unpack('<I',f.read(4))
        try:
            if t==8:
                l,=struct.unpack('<Q',f.read(8)); v=f.read(l).decode('utf8','replace')[:30]
            elif t==9:
                et,=struct.unpack('<I',f.read(4)); c,=struct.unpack('<Q',f.read(8))
                if et==8:
                    for _ in range(c):
                        sl,=struct.unpack('<Q',f.read(8)); f.read(sl)
                else: f.read(S[et]*c)
                v=f"<{c}>"
            else: v=struct.unpack('<'+T[t],f.read(S[t]))[0]
        except KeyError: break
        got[k]=v
    kl_=[v for k,v in got.items() if k.endswith('attention.key_length')]
    hc=[v for k,v in got.items() if k.endswith('attention.head_count')]
    kv=[v for k,v in got.items() if k.endswith('attention.head_count_kv')]
    return f"D={kl_[0] if kl_ else '?'} heads={hc[0] if hc else '?'} kv={kv[0] if kv else '?'}"
for p in sys.argv[1:]:
    print(f"{head(p):32s} {p}")
