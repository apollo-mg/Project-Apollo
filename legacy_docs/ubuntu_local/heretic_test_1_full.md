# Prompt
Write a Python script using bcc (eBPF) to trace all TCP connect() calls on a Linux system, printing the destination IP address and port.

# Response
Here's a Python script using bcc (eBPF) to trace all TCP connect() calls:

```python
#!/usr/bin/env python3
import bcc
from bcc import Table, PerfBufferArray
import ctypes
import socket

# Create a BPF program that traces connect() syscalls
bpf_text = """
#include <uapi/linux/ptrace.h>
#include <bcc/bpf_btf.h>

BPF_PERF_OUTPUT(tcp_connect);

int trace_connect(struct pt_regs *ctx) {
    int ret;
    u32 pid = bpf_get_current_pid_tgid() >> 32;
    u64 flags = bpf_get_current_comm();
    u32 fd = (u32)PT_REGS_PARM1(ctx);
    u32 sock = fd;

    // Get the destination IP and port from the socket buffer
    u32 dest_ip, dest_port;
    if (sock == 0 || sock > 1024) return 0;
    
    struct sock *sk = bpf_get_socket_cookie(ctx);
    if (!sk) return 0;

    // Extract IP and port from socket structure
    u32 l3num, l4num;
    u32 sk_family = sk->sk_family;
    u32 sk_netns_id = sk->sk_netns_id;

    // Determine if it's an IPv4 or IPv6 socket
    if (sk_family == AF_INET) {
        struct sockaddr_in *addr = &((struct sock_common *)sk)->sk_daddr;
        dest_ip = addr->sin_addr.s_addr;
        dest_port = addr->sin_port;
    } else if (sk_family == AF_INET6) {
        struct sockaddr_in6 *addr = &((struct sock_common *)sk)->sk_v6_daddr;
        u32 ip[4];
        bpf_probe_read_kernel(&ip[0], sizeof(ip), &addr->sin6_addr);
        dest_ip = ip[0] << 24 | ip[1] << 16 | ip[2] << 8 | ip[3];
        dest_port = addr->sin6_port;
    } else {
        return 0;
    }

    tcp_connect:submit(&pid, &dest_ip, &dest_port);
    return 0;
}
"""

# Create the BPF program
bpf = bcc.BPF(text=bpf_text)

# Print the destination IP and port for each connect() call
for (pid, dest_ip, dest_port) in bpf["tcp_connect"].iter():
    print(f"PID {pid}: {socket.inet_ntoa(ctypes.c_long(dest_ip).raw)}:{dest_port}")
```

This script:

1. Defines a BPF program that traces `connect()` syscalls using the `trace_connect` function.
2. Extracts the destination IP and port from the socket structure associated with each `connect()` call.
3. Prints the PID, destination IP, and port for each traced connection.

To run this script, make sure you have the `bcc` package installed (`pip install bcc`) and that eBPF is enabled on your system (check with `cat /sys/kernel/debug/trace_pipe`). Then, run the script with elevated privileges (e.g., `sudo python3 trace_connect.py`).