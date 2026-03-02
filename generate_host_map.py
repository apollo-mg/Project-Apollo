import json

hosts = {
    "10.0.0.1": {"name": "Xfinity Gateway", "type": "Gateway", "mac": "", "notes": "MQTT Active"},
    "10.0.0.2": {"name": "Unknown Web Server", "type": "Server", "mac": "", "notes": "Ports 80/443"},
    "10.0.0.5": {"name": "Mark's Linux PC", "type": "Workstation", "mac": "", "notes": "Self (deduced from local IP)"},
    "10.0.0.13": {"name": "Tuya Device 1", "type": "IoT", "mac": "", "notes": "Port 6668"},
    "10.0.0.26": {"name": "Unknown Device 26", "type": "Unknown", "mac": "", "notes": ""},
    "10.0.0.43": {"name": "Unknown Web Server 2", "type": "Server", "mac": "", "notes": "Ports 80/443"},
    "10.0.0.55": {"name": "Tuya Device 55", "type": "IoT", "mac": "", "notes": "Port 6668"},
    "10.0.0.66": {"name": "Mark's Second Monitor", "type": "Smart Plug", "mac": "", "notes": "TP-Link HS103"},
    "10.0.0.82": {"name": "Standing Lamp", "type": "Smart Bulb", "mac": "", "notes": "TP-Link KL125"},
    "10.0.0.83": {"name": "Ender 6 Klipper", "type": "3D Printer", "mac": "", "notes": "Mainsail OS"},
    "10.0.0.86": {"name": "Office Printer / Server", "type": "Printer", "mac": "", "notes": "Ports 80, 8080, 9100"},
    "10.0.0.95": {"name": "Smart TV / Chromecast", "type": "Media", "mac": "", "notes": "Google Cast Ports"},
    "10.0.0.163": {"name": "Tuya Device 163", "type": "IoT", "mac": "", "notes": "Port 6668"},
    "10.0.0.177": {"name": "Security Camera", "type": "Camera", "mac": "", "notes": "RTSP Port 554"},
    "10.0.0.182": {"name": "Tuya Device 182", "type": "IoT", "mac": "", "notes": "Port 6668"},
    "10.0.0.200": {"name": "Mark's Bedroom", "type": "Smart Switch", "mac": "", "notes": "TP-Link HS200"},
    "10.0.0.215": {"name": "Tuya Device 215", "type": "IoT", "mac": "", "notes": "Port 6668"},
    "10.0.0.250": {"name": "Outdoor Plug", "type": "Smart Plug", "mac": "", "notes": "TP-Link EP40 (Default Name)"},
    "10.0.0.251": {"name": "Porch Light Bulb", "type": "Smart Bulb", "mac": "", "notes": "TP-Link KL125"}
}

with open("known_hosts.json", "w") as f:
    json.dump(hosts, f, indent=4)

print("Created known_hosts.json")
