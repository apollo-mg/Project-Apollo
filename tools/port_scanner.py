#!/usr/bin/env python3
"""Lightweight concurrent TCP port scanner."""

import argparse
import socket
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from threading import Lock


@dataclass
class ScanResult:
    port: int
    open: bool = False
    service: str = ""


@dataclass
class ScanStats:
    total: int = 0
    open_count: int = 0
    closed_count: int = 0
    start_time: float = field(default=0.0, repr=False)
    end_time: float = field(default=0.0, repr=False)
    _lock: Lock = field(default=Lock(), repr=False)

    def record_open(self, port: int, service: str = ""):
        with self._lock:
            self.open_count += 1

    def record_closed(self):
        with self._lock:
            self.closed_count += 1

    def finish(self):
        self.end_time = time.time()
        self.total = self.open_count + self.closed_count


def scan_port(target: str, port: int, timeout: float = 1.0) -> ScanResult:
    """Scan a single port. Returns a ScanResult."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((target, port))
        sock.close()
        if result == 0:
            service = ""
            try:
                service = socket.getservbyport(port)
            except OSError:
                pass
            return ScanResult(port=port, open=True, service=service)
        return ScanResult(port=port, open=False)
    except (socket.error, OSError):
        return ScanResult(port=port, open=False)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Lightweight concurrent TCP port scanner"
    )
    parser.add_argument("target", help="Target IP address or hostname")
    parser.add_argument(
        "port_start", type=int, help="Start port (inclusive)"
    )
    parser.add_argument(
        "port_end", type=int, help="End port (inclusive)"
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=1.0,
        help="Connection timeout in seconds (default: 1.0)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=100,
        help="Max concurrent threads (default: 100)",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    if args.port_start < 0 or args.port_end > 65535:
        print("Error: Port range must be between 0 and 65535.", file=sys.stderr)
        sys.exit(1)

    if args.port_start > args.port_end:
        print("Error: port_start must be <= port_end.", file=sys.stderr)
        sys.exit(1)

    if args.workers < 1:
        print("Error: --workers must be at least 1.", file=sys.stderr)
        sys.exit(1)

    stats = ScanStats()
    stats.start_time = time.time()

    ports = list(range(args.port_start, args.port_end + 1))
    print(f"Scanning {args.target}: ports {args.port_start}-{args.port_end} "
          f"({len(ports)} ports) | timeout={args.timeout}s | workers={args.workers}")
    print("-" * 60)

    open_ports: list[ScanResult] = []

    try:
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            futures = {
                executor.submit(scan_port, args.target, port, args.timeout): port
                for port in ports
            }
            for future in as_completed(futures):
                port = futures[future]
                try:
                    result = future.result()
                except Exception:
                    stats.record_closed()
                    continue

                if result.open:
                    stats.record_open(result.port, result.service)
                    open_ports.append(result)
                else:
                    stats.record_closed()
    except KeyboardInterrupt:
        print("\n\nScan interrupted by user. Shutting down...")
        sys.exit(130)

    stats.finish()

    print("-" * 60)
    if open_ports:
        print("Open ports found:")
        for r in sorted(open_ports, key=lambda x: x.port):
            svc = f" - {r.service}" if r.service else ""
            print(f"  OPEN: {r.port}{svc}")
    else:
        print("No open ports found in the scanned range.")

    print("-" * 60)
    elapsed = stats.end_time - stats.start_time
    print(f"Summary: {stats.total} scanned | {stats.open_count} open | "
          f"{stats.closed_count} closed | {elapsed:.2f}s elapsed")


if __name__ == "__main__":
    main()
