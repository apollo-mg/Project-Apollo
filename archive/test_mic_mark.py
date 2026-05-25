from pvrecorder import PvRecorder
print("Scanning Audio Devices...")
try:
    devices = PvRecorder.get_available_devices()
    for index, device in enumerate(devices):
        print(f"Index: {index}, Device: {device}")
except Exception as e:
    print(f"Error scanning devices: {e}")
