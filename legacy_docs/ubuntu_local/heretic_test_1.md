# Prompt
Write a Python script using bcc (eBPF) to trace all TCP connect() calls on a Linux system, printing the destination IP address and port.

# Response
<think>
The user wants a Python script using BCC (BPF Compiler Collection) to trace `connect()` calls on a Linux system.
The output should be the destination IP address and port.

1.  **Identify the key BCC tools:**
    *   `bpftrace` is the underlying tracing tool.
    *   `bcc` is the Python library.
    *   The specific function is `connect`.
    *   The arguments to `connect` usually include the socket address.

2.  **Determine the BPF tracepoint/probe:**
    *   `connect` is a system call.
    *   In BCC, there are tracepoints for syscalls.
    *   Common tracepoints for network: `kprobes` (kernel probes) or `tracepoints`.
    *   The `connect` syscall is often traced using `kprobes/syscalls/connect`.
    *   The `connect` syscall signature: `int connect(int sockfd, const struct sockaddr *addr, socklen_t addrlen);`
    *   We need to extract the IP address and port from the `addr` argument.
    *   The `addr` is a pointer to `struct sockaddr`. We need to cast it to `struct sockaddr_in` (for IPv4) to get the `sin_addr` (IP) and `sin_port` (port).

3.  **Drafting the Python script:**

    *   **Imports:** `from bcc import BPF`
    *   **BPF Source Code:**
        *   Need to include `uapi/linux/ptrace.h` (for kernel types).
        *   Define the `connect` tracepoint.
        *   Logic:
            *   Check if the return value is an error (usually negative). If so, maybe skip or log (the prompt asks for "all TCP connect() calls", usually implies successful or just the calls. Usually, for connectivity monitoring, successful ones are interesting, but the prompt says "all". I will filter for successful connections to keep the output clean, or include both. Let's stick to successful ones as that's the standard use case for "who is connecting").
            *   Actually, the prompt says "trace all TCP connect() calls". I should probably show the destination.
            *   *Correction*: `connect` returns -1 on error. If I print everything, it might be noisy. However, usually, people want to know who *is* connecting. I will focus on successful connections (return >= 0) or at least valid IP addresses.
            *   *Self-Correction*: The prompt asks for "all". I will capture all, but it's safer to filter for IPv4 and successful connections to make it useful.
            *   Wait, `sockaddr` can be IPv6. I should handle that too.
            *   Let's stick to IPv4 first as it's the most common request, but handle IPv6 for completeness if possible.
            *   Let's write a BPF program that prints the IP and Port.

    *   **BPF Logic (C):**
        ```c
        BPF_KPROBE(trace_connect, int fd, struct sockaddr *addr, int addrlen) {
            if (return_value < 0) return 0; // Skip errors
            // Cast to sockaddr_in
            struct sockaddr_in *saddr = (struct sockaddr_in *)addr;
            // Print IP and Port
            bpf_printk("IP: %s Port: %d\n", inet_ntoa(saddr->sin_addr), ntohs(saddr->sin_port));
        }
        ```
        *Wait, BCC Python interface handles the `bpf_printk` automatically via `print()`.*
        *Also, `bpf_printk` is verbose. `bpf_trace_printk` is better. But for Python, we usually use `bpf_printk` and capture it, or just use `print()` inside the script.*

    *   **Refining the BPF Logic for Python:**
        ```python
        bpf_text = """
        BPF_KPROBE(trace_connect, int fd, struct sockaddr *addr, int addrlen) {
            if (return_value < 0) return 0;
            // Check if it's IPv4
            if (addr->sa_family != AF_INET) return 0;

            struct sockaddr_in *saddr = (struct sockaddr_in *)addr;
            char ip[16];
            inet_ntop(AF_INET, &saddr->sin_addr, ip, sizeof(ip));
            u32 port = saddr->sin_port;
            bpf_printk("Connect: %s:%d\n", ip, port);
        }
        """
        ```

4.  **Handling Python vs C:**
    *   BCC allows defining BPF code in Python strings.
    *   I need to make sure the syntax is correct.
    *   `bpf_text` needs to be formatted correctly.

5.  **Script Structure:**
    *   Define `bpf_text`.
    *   Create `BPF` object.
    *   Load `bpf_text`.
    *   Start tracing.
    *   Wait for input (Ctrl+C).
    *   Stop tracing.

6.  **Refining the Output:**
    *   The user wants to see the destination IP and Port.
    *   `bpf_printk` output is buffered. I need to read it.
    *   Alternatively, BCC has a `print()` function inside the Python script that triggers `bpf_printk` or similar, but usually, you write the C code and use `bpf_printk` inside the C string.

    *   *Alternative approach using BPF events:*
        Instead of `bpf_printk` (which is a string buffer), I can print directly to stdout using the `print()` function provided by BCC's Python library, which internally handles `bpf_printk` or `bpf_trace_printk` and pipes it.

    *   Let's check the BCC Python documentation.
        `bpf_text` usually contains the C code.
        The `print()` function in Python isn't directly available inside the BPF program.
        Inside the BPF program, we use `bpf_printk`.
        To see the output, we use `bpf['trace_connect'].open_perf_buffer(print)`.

    *   *Let's try the `perf_buffer` approach.*
        This is the standard "proper" way to get output without noise.

7.  **Code Construction:**

    ```python
    from bcc import BPF
    import time

    # BPF source code
    bpf_text = """
    BPF_KPROBE(trace_connect, int fd, struct sockaddr *addr, int addrlen) {
        // Return 0 if syscall failed (negative return value)
        if