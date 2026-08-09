#!/usr/bin/env python3
"""G1-compliant re-run: perf level pinned high, clocks sampled DURING each timed
region by a background thread rather than at arm boundaries (the first pass
sampled at boundaries and caught idle downclocks, not the working state)."""
import json, subprocess, threading, time
import torch

SHAPES = [1024, 2048, 4096, 8192]
REPEATS = 5
ITERS, WARMUP = 30, 10


def sample():
    try:
        out = subprocess.run(['rocm-smi', '--showclocks', '--showpower'],
                             capture_output=True, text=True, timeout=10).stdout
    except Exception:
        return None
    d = {}
    for line in out.splitlines():
        low = line.lower()
        if 'sclk clock level' in low:
            d['sclk'] = int(line.split('(')[-1].split('Mhz')[0])
        elif 'graphics package power' in low:
            d['pw'] = float(line.split(':')[-1].strip())
    return d or None


class Watcher:
    def __init__(self):
        self.samples, self._stop = [], threading.Event()
        self.t = threading.Thread(target=self._loop, daemon=True)

    def _loop(self):
        while not self._stop.is_set():
            s = sample()
            if s:
                self.samples.append(s)
            self._stop.wait(0.25)

    def __enter__(self):
        self.t.start(); return self

    def __exit__(self, *a):
        self._stop.set(); self.t.join(timeout=2)

    def stats(self):
        s = [x['sclk'] for x in self.samples if 'sclk' in x]
        p = [x['pw'] for x in self.samples if 'pw' in x]
        if not s:
            return {}
        return {'sclk_min': min(s), 'sclk_max': max(s), 'sclk_med': sorted(s)[len(s)//2],
                'spread_pct': round((max(s)-min(s))/max(s)*100, 1),
                'pw_max': max(p) if p else None, 'n': len(s)}


def timed(fn):
    for _ in range(WARMUP):
        fn()
    torch.cuda.synchronize()
    t = time.perf_counter()
    for _ in range(ITERS):
        fn()
    torch.cuda.synchronize()
    return (time.perf_counter() - t) / ITERS


def main():
    FP8 = torch.float8_e4m3fnuz
    res = {'torch': torch.__version__, 'hip': torch.version.hip,
           'perflevel': 'high (pinned)', 'runs': []}

    for n in SHAPES:
        arms = {}
        for name, dt in (('fp32', torch.float32), ('fp16', torch.float16), ('bf16', torch.bfloat16)):
            a = torch.randn(n, n, device='cuda', dtype=dt)
            b = torch.randn(n, n, device='cuda', dtype=dt)
            arms[name] = lambda a=a, b=b: a @ b
        a8 = torch.randn(n, n, device='cuda').to(FP8)
        b8 = torch.randn(n, n, device='cuda').t().contiguous().t().to(FP8)
        sc = torch.tensor(1.0, device='cuda')
        arms['fp8_e4m3fnuz'] = lambda: torch._scaled_mm(a8, b8, scale_a=sc, scale_b=sc,
                                                        out_dtype=torch.bfloat16)

        for name, fn in arms.items():
            for rep in range(REPEATS):
                try:
                    with Watcher() as w:
                        s = timed(fn)
                    res['runs'].append({'shape': n, 'dtype': name, 'rep': rep, 'sec': s,
                                        'tflops': 2 * n ** 3 / s / 1e12, 'clk': w.stats()})
                except Exception as e:
                    res['runs'].append({'shape': n, 'dtype': name, 'rep': rep,
                                        'error': f'{type(e).__name__}: {str(e)[:100]}'})
        torch.cuda.empty_cache()

    print(json.dumps(res))


if __name__ == '__main__':
    main()
