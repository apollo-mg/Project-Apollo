#!/usr/bin/env python3
"""portscan.py — lightweight multi-threaded TCP port scanner with live performance metrics.

Usage:
    ./portscan.py --host 127.0.0.1 --ports 8080-8100,443 --workers 64
    ./portscan.py --host 10.0.0.73 --ports 1-1024 --workers 256 --timeout 1.0

Metrics printed live during the scan and as a final summary:
    ports scanned, open/closed counts, live and average ports/sec,
    RTT of open ports (min/median/max), total elapsed time.

Standard library only. No dependencies.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from socket import create_connection, timeout as SocketTimeout
from typing import Iterable


def parse_ports(spec: str) -> list[int]:
    """Parse '1-1024,8080,9000-9010' into a flat, deduped, sorted list."""
    ports: set[int] = set()
    for chunk in spec.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "-" in chunk:
            lo, hi = (int(x) for x in chunk.split("-", 1))
            if lo > hi:
                lo, hi = hi, lo
            ports.update(range(lo, hi + 1))
        else:
            ports.add(int(chunk))
    bad = [p for p in ports if not (0 < p < 65536)]
    if bad:
        raise SystemExit(f"port numbers must be 1-65535: {sorted(set(bad))}")
    return sorted(ports)


def probe(host: str, port: int, timeout: float) -> tuple[int, bool, float]:
    """Connect to host:port. Returns (port, is_open, elapsed_seconds)."""
    t0 = time.perf_counter()
    try:
        sock = create_connection((host, port), timeout=timeout)
        elapsed = time.perf_counter() - t0
        sock.close()
        return port, True, elapsed
    except (OSError, SocketTimeout):
        return port, False, time.perf_counter() - t0


def scan(host: str, ports: Iterable[int], workers: int, timeout: float) -> dict:
    ports = list(ports)
    total = len(ports)
    opened: list[int] = []
    rtt: list[float] = []
    t_start = time.monotonic()
    last_report = t_start
    scanned = 0

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for port, is_open, elapsed in pool.map(lambda p: probe(host, p, timeout), ports):
            scanned += 1
            if is_open:
                opened.append(port)
                rtt.append(elapsed)
            now = time.monotonic()
            if now - last_report >= 1.0:
                live_rate = scanned / (now - t_start)
                print(
                    f"  [{scanned:>5}/{total}] open={len(opened):>3} "
                    f"rate={live_rate:7.1f} ports/s",
                    file=sys.stderr,
                )
                last_report = now

    elapsed_total = time.monotonic() - t_start
    summary = {
        "host": host,
        "ports_scanned": total,
        "open_ports": opened,
        "open_count": len(opened),
        "closed_count": total - len(opened),
        "elapsed_seconds": round(elapsed_total, 3),
        "throughput_ports_per_sec": round(total / elapsed_total, 2) if elapsed_total > 0 else None,
        "open_rtt_seconds": {
            "min": round(min(rtt), 6) if rtt else None,
            "median": round(statistics.median(rtt), 6) if rtt else None,
            "max": round(max(rtt), 6) if rtt else None,
        },
    }
    return summary


def main() -> None:
    ap = argparse.ArgumentParser(description="Multi-threaded TCP port scanner with live metrics.")
    ap.add_argument("--host", default="127.0.0.1", help="target host (default 127.0.0.1)")
    ap.add_argument("--ports", default="1-1024", help="'lo-hi,lo-hi,port,...' (default 1-1024)")
    ap.add_argument("--workers", type=int, default=64, help="thread pool size (default 64)")
    ap.add_argument("--timeout", type=float, default=1.0, help="per-probe timeout in seconds (default 1.0)")
    ap.add_argument("--json-out", metavar="FILE", help="write summary JSON to FILE (stdout stays clean)")
    args = ap.parse_args()

    ports = parse_ports(args.ports)
    print(
        f"scanning {args.host} ports {ports[0]}-{ports[-1]} "
        f"({len(ports)} ports, {args.workers} workers, {args.timeout}s timeout)",
        file=sys.stderr,
    )
    summary = scan(args.host, ports, args.workers, args.timeout)

    if args.json_out:
        with open(args.json_out, "w") as f:
            json.dump(summary, f, indent=2)
        print(f"summary written to {args.json_out}", file=sys.stderr)

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
