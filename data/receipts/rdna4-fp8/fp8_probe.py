# Does PyTorch+ROCm on this gfx1201 run FP8 GEMM natively (torch._scaled_mm), and is it faster than bf16?
import torch, time
dev = "cuda"
print("torch", torch.__version__, "hip", torch.version.hip, torch.cuda.get_device_properties(0).gcnArchName)
M = N = K = 8192
a = torch.randn(M, K, device=dev, dtype=torch.bfloat16)
b = torch.randn(N, K, device=dev, dtype=torch.bfloat16)
def bench(fn, n=20):
    fn(); torch.cuda.synchronize()
    t = time.perf_counter()
    for _ in range(n): fn()
    torch.cuda.synchronize()
    dt = (time.perf_counter() - t) / n
    return 2 * M * N * K / dt / 1e12
print(f"bf16 matmul: {bench(lambda: a @ b.t()):.1f} TFLOPS")
for fmt in ("float8_e4m3fn", "float8_e4m3fnuz"):
    dt8 = getattr(torch, fmt, None)
    if dt8 is None:
        print(fmt, "not in this torch"); continue
    try:
        a8, b8 = a.to(dt8), b.to(dt8)
        one = torch.tensor(1.0, device=dev)
        out = torch._scaled_mm(a8, b8.t(), scale_a=one, scale_b=one, out_dtype=torch.bfloat16)
        ref = (a8.to(torch.bfloat16) @ b8.to(torch.bfloat16).t())
        err = ((out.float() - ref.float()).abs().max() / ref.float().abs().max()).item()
        tf = bench(lambda: torch._scaled_mm(a8, b8.t(), scale_a=one, scale_b=one, out_dtype=torch.bfloat16))
        print(f"{fmt} _scaled_mm: OK, {tf:.1f} TFLOPS, max rel err vs upcast {err:.2e}")
    except Exception as e:
        print(f"{fmt} _scaled_mm: FAILED: {type(e).__name__}: {str(e)[:200]}")
try:
    ai, bi = torch.randint(-64, 64, (M, K), device=dev, dtype=torch.int8), torch.randint(-64, 64, (N, K), device=dev, dtype=torch.int8)
    tf = bench(lambda: torch._int_mm(ai, bi.t()))
    print(f"int8 _int_mm: OK, {tf:.1f} TOPS")
except Exception as e:
    print(f"int8 _int_mm: FAILED: {type(e).__name__}: {str(e)[:200]}")
