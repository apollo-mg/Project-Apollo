import socket
import subprocess
import threading
import ipaddress
import time
import requests
import re
import sys

# Get local IP and determine subnet
def get_local_subnet():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        # Assume /24 for simplicity unless interface lookup
        return f"{local_ip.rsplit('.', 1)[0]}.0/24"
    except Exception:
        return "10.0.0.0/24"

SUBNET = get_local_subnet()
COMMON_PORTS = {
    9999: "TP-Link Kasa",
    80: "HTTP (Web UI)",
    443: "HTTPS",
    8080: "HTTP Alt",
    554: "RTSP (Camera)",
    8008: "Google Cast",
    8009: "Google Cast",
    3000: "Development/Generic",
    1883: "MQTT",
    5000: "UPnP/Flask",
    9100: "Printer",
    6668: "Tuya (Generic)",
    34567: "Tuya (Legacy)"
}

lock = threading.Lock()
active_hosts = []

def get_http_title(ip, port):
    try:
        protocol = "https" if port == 443 else "http"
        url = f"{protocol}://{ip}:{port}"
        response = requests.get(url, timeout=1)
        if response.status_code == 200:
            # Simple title extraction
            content = response.text
            start = content.find("<title>")
            end = content.find("</title>")
            if start != -1 and end != -1:
                return content[start+7:end].strip()
    except:
        pass
    return None

def scan_host(ip):
    # Ping first
    try:
        # Cross-platform ping
        if sys.platform == "win32":
            subprocess.check_output(["ping", "-n", "1", "-w", "500", str(ip)], stderr=subprocess.STDOUT)
        else:
            subprocess.check_output(["ping", "-c", "1", "-W", "1", str(ip)], stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError:
        return

    # If ping answers, check ports
    open_ports = []
    device_name = "Unknown"
    
    for port, desc in COMMON_PORTS.items():
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.3) # Fast timeout
        result = s.connect_ex((str(ip), port))
        if result == 0:
            open_ports.append(f"{port} ({desc})")
            if port in [80, 8080]:
                title = get_http_title(str(ip), port)
                if title:
                    device_name = f"Web: {title}"
        s.close()
    
    with lock:
        print(f"FOUND: {ip} | Ports: {', '.join(open_ports)} | Info: {device_name}")
        active_hosts.append({"ip": str(ip), "ports": open_ports, "info": device_name})

def main():
    print(f"Scanning {SUBNET}...")
    threads = []
    # Create network object
    network = ipaddress.ip_network(SUBNET)
    
    # Skip network and broadcast
    hosts = list(network.hosts())
    
    # Chunking to avoid too many threads at once
    chunk_size = 50
    for i in range(0, len(hosts), chunk_size):
        chunk = hosts[i:i+chunk_size]
        current_batch = []
        for ip in chunk:
            t = threading.Thread(target=scan_host, args=(ip,))
            t.start()
            current_batch.append(t)
        
        for t in current_batch:
            t.join()

    print("\nScan Complete.")

if __name__ == "__main__":
    main()
