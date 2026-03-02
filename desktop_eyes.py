import subprocess
import os
import time
import platform

def capture_screen(filename="latest_screenshot.png"):
    """
    Captures the primary monitor and saves it to the specified filename.
    Returns the absolute path to the screenshot.
    """
    output_path = os.path.abspath(filename)
    try:
        if platform.system() == "Windows":
            from PIL import ImageGrab
            screenshot = ImageGrab.grab()
            screenshot.save(output_path)
            print(f"Screenshot saved to: {output_path}")
            return output_path
        else:
            # Use spectacle for capture (KDE native, works on X11 and Wayland)
            subprocess.run(["spectacle", "-b", "-n", "-o", output_path], check=True)
            print(f"Screenshot saved to: {output_path}")
            return output_path
    except subprocess.CalledProcessError as e:
        print(f"Capture failed: {e}")
        raise e
    except Exception as e:
        print(f"Error capturing screen: {e}")
        raise e

if __name__ == "__main__":
    capture_screen()
