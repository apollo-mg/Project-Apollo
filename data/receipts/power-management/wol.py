#!/usr/bin/env python3
"""Send a Wake-on-LAN magic packet. No package install -- it is 6x0xFF + 16x the MAC,
broadcast to UDP 9. Written inline so the wake path has no dependency to rot."""
import socket, sys
mac = sys.argv[1].replace(":", "").replace("-", "")
bcast = sys.argv[2] if len(sys.argv) > 2 else "10.0.0.255"
pkt = b"\xff" * 6 + bytes.fromhex(mac) * 16
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
for port in (9, 7):
    s.sendto(pkt, (bcast, port))
print(f"magic packet sent to {mac} via {bcast}:9,7")
