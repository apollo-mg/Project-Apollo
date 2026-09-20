import torch, triton, triton.language as tl
print("triton", triton.__version__, "| torch", torch.__version__)
print("device", torch.cuda.get_device_name(0), torch.cuda.get_device_capability(0))

@triton.jit
def matmul_k(A, B, C, M, N, K, BM: tl.constexpr, BN: tl.constexpr, BK: tl.constexpr):
    pm, pn = tl.program_id(0), tl.program_id(1)
    offm = pm * BM + tl.arange(0, BM)
    offn = pn * BN + tl.arange(0, BN)
    acc = tl.zeros((BM, BN), dtype=tl.float32)
    for k in range(0, K, BK):
        offk = k + tl.arange(0, BK)
        a = tl.load(A + offm[:, None] * K + offk[None, :], mask=(offm[:, None] < M) & (offk[None, :] < K), other=0.0)
        b = tl.load(B + offk[:, None] * N + offn[None, :], mask=(offk[:, None] < K) & (offn[None, :] < N), other=0.0)
        acc += tl.dot(a, b)          # <-- the tensor-core op
    tl.store(C + offm[:, None] * N + offn[None, :], acc, mask=(offm[:, None] < M) & (offn[None, :] < N))

M = N = K = 128
a = torch.randn((M, K), device="cuda", dtype=torch.float16)
b = torch.randn((K, N), device="cuda", dtype=torch.float16)
c = torch.zeros((M, N), device="cuda", dtype=torch.float32)
try:
    matmul_k[(1, 1)](a, b, c, M, N, K, BM=M, BN=N, BK=K)
    torch.cuda.synchronize()
    ref = (a.float() @ b.float())
    err = (c - ref).abs().max().item()
    print("TRITON tl.dot ON sm_60: OK, max abs err vs torch =", err)
except Exception as e:
    print("TRITON tl.dot ON sm_60: FAILED")
    print(type(e).__name__, str(e)[:600])
