def main_loop():
    try:
        # Prioritize C922 (Index 4) for Wake Word (More reliable driver support)
        device_index = -1
        devices = PvRecorder.get_available_devices()
        for i, dev in enumerate(devices):
            if "C922" in dev:
                 device_index = i
                 print(f"✅ Using Wake Word Mic: {dev} (Index {i})")
                 break
            elif "Playstation Eye" in dev or "Sony" in dev:
                device_index = i
                print(f"✅ Using Wake Word Mic: {dev} (Index {i})")
                break
            elif "Shop_Ears" in dev:
                device_index = i
                print(f"✅ Using Wake Word Mic: {dev} (Index {i})")
                break            
        recorder = PvRecorder(frame_length=512, device_index=device_index)
    except Exception as e:
        print(f"Failed to init default device: {e}")
        return
