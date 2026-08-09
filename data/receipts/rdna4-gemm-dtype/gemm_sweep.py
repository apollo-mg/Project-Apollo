#!/usr/bin/env python3
"""RDNA4 GEMM throughput by dtype x shape x BLAS backend.

Gates enforced here, not in the analysis:
  G1 clocks recorded per arm      G2 correctness before throughput
  G3 allocation outside the timed region
"""
import json, os, subprocess, sys, time
import torch

SHAPES = [1024, 2048, 4096, 8192]
REPEATS = 3          # K>1: report median, keep spread
ITERS, WARMUP = 30, 10


def clocks():
    try:
        out = subprocess.run(['rocm-smi', '--showclocks', '--showpower', '--showtemp'],
                             capture_output=True, text=True, timeout=15).stdout
    except Exception:
        return {}
    d = {}
    for line in out.splitlines():
        low = line.lower()
        if 'sclk clock level' in low:
            d['sclk_mhz'] = int(line.split('(')[-1].split('Mhz')[0])
        elif 'mclk clock level' in low:
            d['mclk_mhz'] = int(line.split('(')[-1].split('Mhz')[0])
        elif 'graphics package power' in low:
            d['power_w'] = float(line.split(':')[-1].strip())
        elif 'sensor edge' in low:
            d['temp_c'] = float(line.split(':')[-1].strip())
    return d


def timed(fn):
    for _ in range(WARMUP):
        fn()
    torch.cuda.synchronize()
    t = time.perf_counter()
    for _ in range(ITERS):
        fn()
    torch.cuda.synchronize()
    return (time.perf_counter() - t) / ITERS


def correctness(dt, n=512):
    """G2. Compare against an fp32 reference computed on the same device."""
    torch.manual_seed(0)
    a32 = torch.randn(n, n, device='cuda')
    b32 = torch.randn(n, n, device='cuda')
    ref = (a32 @ b32).float()
    got = (a32.to(dt) @ b32.to(dt)).float()
    denom = ref.abs().mean().item()
    return float((got - ref).abs().mean().item() / denom)


def fp8_correctness(dt, n=512):
    torch.manual_seed(0)
    a32 = torch.randn(n, n, device='cuda')
    b32 = torch.randn(n, n, device='cuda')
    ref = (a32 @ b32).float()
    sc = torch.tensor(1.0, device='cuda')
    a8 = a32.to(dt)
    b8 = b32.t().contiguous().t().to(dt)
    got = torch._scaled_mm(a8, b8, scale_a=sc, scale_b=sc, out_dtype=torch.bfloat16).float()
    denom = ref.abs().mean().item()
    return float((got - ref).abs().mean().item() / denom)


def run_dtype(dt, n):
    a = torch.randn(n, n, device='cuda', dtype=dt)
    b = torch.randn(n, n, device='cuda', dtype=dt)
    torch.cuda.synchronize()
    return timed(lambda: a @ b)


def run_fp8(dt, n):
    sc = torch.tensor(1.0, device='cuda')
    a = torch.randn(n, n, device='cuda').to(dt)
    b = torch.randn(n, n, device='cuda').t().contiguous().t().to(dt)
    torch.cuda.synchronize()
    return timed(lambda: torch._scaled_mm(a, b, scale_a=sc, scale_b=sc, out_dtype=torch.bfloat16))


def main():
    backend = os.environ.get('ARM_BACKEND', 'default')
    results = {
        'backend': backend,
        'torch': torch.__version__,
        'hip': torch.version.hip,
        'device': torch.cuda.get_device_name(0),
        'arch': torch.cuda.get_device_properties(0).gcnArchName,
        'arch_list': torch.cuda.get_arch_list(),
        'preferred_blas': str(torch.backends.cuda.preferred_blas_library()),
        'env': {k: v for k, v in os.environ.items()
                if k.startswith(('TORCH_BLAS', 'HIPBLASLT', 'ROCBLAS', 'HSA_', 'PYTORCH_TUNABLE'))},
        'clocks_start': clocks(),
        'runs': [],
        'correctness': {},
    }

    dtypes = [('fp32', torch.float32), ('fp16', torch.float16), ('bf16', torch.bfloat16)]
    fp8s = [(n, getattr(torch, n)) for n in ('float8_e4m3fnuz', 'float8_e4m3fn')
            if hasattr(torch, n)]

    # G2 first -- a dtype that fails correctness still gets timed, but the receipt
    # records the error so a fast wrong kernel cannot be quoted as a win.
    for name, dt in dtypes:
        try:
            results['correctness'][name] = correctness(dt)
        except Exception as e:
            results['correctness'][name] = f'FAILED: {type(e).__name__}: {e}'
    for name, dt in fp8s:
        try:
            results['correctness'][name] = fp8_correctness(dt)
        except Exception as e:
            results['correctness'][name] = f'FAILED: {type(e).__name__}: {e}'

    for n in SHAPES:
        for name, dt in dtypes:
            for rep in range(REPEATS):
                try:
                    s = run_dtype(dt, n)
                    results['runs'].append({'shape': n, 'dtype': name, 'rep': rep,
                                            'sec': s, 'tflops': 2 * n ** 3 / s / 1e12,
                                            'clocks': clocks() if rep == 0 else None})
                except Exception as e:
                    results['runs'].append({'shape': n, 'dtype': name, 'rep': rep,
                                            'error': f'{type(e).__name__}: {str(e)[:120]}'})
        for name, dt in fp8s:
            for rep in range(REPEATS):
                try:
                    s = run_fp8(dt, n)
                    results['runs'].append({'shape': n, 'dtype': name, 'rep': rep,
                                            'sec': s, 'tflops': 2 * n ** 3 / s / 1e12,
                                            'clocks': clocks() if rep == 0 else None})
                except Exception as e:
                    results['runs'].append({'shape': n, 'dtype': name, 'rep': rep,
                                            'error': f'{type(e).__name__}: {str(e)[:120]}'})
        torch.cuda.empty_cache()

    results['clocks_end'] = clocks()
    print(json.dumps(results))


if __name__ == '__main__':
    main()
