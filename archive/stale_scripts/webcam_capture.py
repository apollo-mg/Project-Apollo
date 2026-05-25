import cv2
import sys
import os
import time

SAVE_PATH = "tmp/webcam_capture.jpg"
os.makedirs(os.path.dirname(SAVE_PATH), exist_ok=True)

def capture_webcam(device_index=0):
    try:
        # 1. Open Capture
        cap = cv2.VideoCapture(device_index)
        if not cap.isOpened():
            print(f"Error: Could not open video device {device_index}")
            return False

        # 2. Wait for Auto-Expose (2 sec)
        start = time.time()
        while time.time() - start < 2.0:
            ret, frame = cap.read()
            if not ret: break
        
        # 3. Capture Frame
        ret, frame = cap.read()
        cap.release()

        if ret:
            # Save Image
            cv2.imwrite(SAVE_PATH, frame)
            print(f"Capture successful: {SAVE_PATH}")
            return True
        else:
            print("Error: Could not read frame.")
            return False
            
    except Exception as e:
        print(f"Capture Error: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) > 1:
        dev_idx = int(sys.argv[1])
    else:
        # Try finding C922 (or default)
        dev_idx = 0
        # If /dev/video2 exists and video0 failed, try it? 
        # But default 0 is usually fine for primary webcam.
    
    success = capture_webcam(dev_idx)
    sys.exit(0 if success else 1)
