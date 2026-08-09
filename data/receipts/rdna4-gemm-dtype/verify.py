#!/usr/bin/env python3
"""Re-test the two rdna4-gemm-dtype findings on a newer wheel.

  1. Is torch._scaled_mm(e4m3fnuz) still exactly 4x too large?
  2. Is fp16 still 1.7-2.3x slower than bf16?

Same controls as the receipt: correctness is checked against the SAME quantized
values multiplied in fp32, which separates kernel error from fp8 precision loss.
"""
import json, subprocess, time
import torch

out = {'torch': torch.__version__, 'hip': torch.version.hip,
       'device': torch.cuda.get_device_name(0),
       'arch': torch.cuda.get_device_properties(0).gcnArchName,
       'arch_list': torch.cuda.get_arch_list()}

# --- Finding 1: the 4x --------------------------------------------------------
fp8_results = {}
for name in ('float8_e4m3fnuz', 'float8_e4m3fn'):
    dt = getattr(torch, name, None)
    if dt is None:
        fp8_results[name] = 'dtype absent from this torch'
        continue
    try:
        torch.manual_seed(0)
        n = 256
        a32 = torch.randn(n, n, device='cuda')
        b32 = torch.randn(n, n, device='cuda')
        a8 = a32.to(dt)
        b8 = b32.t().contiguous().t().to(dt)
        deq = a8.float() @ b8.float()          # same values, fp32 math
        sc = torch.tensor(1.0, device='cuda')
        got = torch._scaled_mm(a8, b8, scale_a=sc, scale_b=sc, out_dtype=torch.float32)
        ratio = (got / deq)
        fp8_results[name] = {
            'ratio_mean': ratio.mean().item(),
            'ratio_std': ratio.std().item(),
            'corr': torch.corrcoef(torch.stack([got.flatten(), deq.flatten()]))[0, 1].item(),
            'rel_err_vs_dequant_ref': ((got - deq).abs().mean() / deq.abs().mean()).item(),
            'fp8_quant_cost': ((deq - a32 @ b32).abs().mean() / (a32 @ b32).abs().mean()).item(),
        }
    except Exception as e:
        fp8_results[name] = f'FAILED: {type(e).__name__}: {str(e)[:120]}'
out['fp8'] = fp8_results

# --- Finding 2: the fp16 gap --------------------------------------------------
def timed(fn, iters=30, warmup=10):
    for _ in range(warmup): fn()
    torch.cuda.synchronize(); t = time.perf_counter()
    for _ in range(iters): fn()
    torch.cuda.synchronize()
    return (time.perf_counter() - t) / iters

gemm = {}
for n in (1024, 2048, 4096, 8192):
    row = {}
    for nm, dt in (('fp32', torch.float32), ('fp16', torch.float16), ('bf16', torch.bfloat16)):
        try:
            a = torch.randn(n, n, device='cuda', dtype=dt)
            b = torch.randn(n, n, device='cuda', dtype=dt)
            row[nm] = round(2 * n**3 / timed(lambda: a @ b) / 1e12, 1)
        except Exception as e:
            row[nm] = f'ERR {type(e).__name__}'
    try:
        dt = torch.float8_e4m3fnuz
        a8 = torch.randn(n, n, device='cuda').to(dt)
        b8 = torch.randn(n, n, device='cuda').t().contiguous().t().to(dt)
        sc = torch.tensor(1.0, device='cuda')
        row['fp8'] = round(2 * n**3 / timed(lambda: torch._scaled_mm(a8, b8, scale_a=sc, scale_b=sc, out_dtype=torch.bfloat16)) / 1e12, 1)
    except Exception as e:
        row['fp8'] = f'ERR {type(e).__name__}'
    if isinstance(row.get('fp16'), float) and isinstance(row.get('bf16'), float) and row['fp16']:
        row['bf16_over_fp16'] = round(row['bf16'] / row['fp16'], 2)
    gemm[n] = row
    torch.cuda.empty_cache()
out['gemm'] = gemm

print(json.dumps(out, indent=2))
