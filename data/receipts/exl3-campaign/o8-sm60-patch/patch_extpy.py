p = "/home/mark/exl3quant/lib/python3.13/site-packages/exllamav3/ext.py"
s = open(p).read()
marker = "    exllamav3_ext = load("
inject = ('    # sm_60 (Tesla P100) patch: force-include shims for __dp4a (sm_61) and\n'
          '    # __nanosleep (sm_70), neither of which exists on GP100.\n'
          '    extra_cuda_cflags += ["-include", "/home/mark/exl3_sm60_compat.cuh"]\n\n')
if "exl3_sm60_compat.cuh" in s:
    print("already patched")
else:
    assert s.count(marker) == 1, s.count(marker)
    s = s.replace(marker, inject + marker)
    open(p, "w").write(s)
    print("ext.py patched")
