import os
import time
import sys
from modules.dashboard import get_dashboard

def run_live_dashboard():
    """
    Simple refresh loop for the Apollo Dashboard.
    Uses 'clear' to provide a 'live' terminal experience.
    """
    try:
        # Hide cursor
        print("\033[?25l", end="")
        while True:
            # Move cursor to top-left (Home)
            print("\033[H", end="")
            
            # Get the latest dashboard report
            report = get_dashboard()
            
            # Print to stdout, clearing each line's tail to handle shrinking content
            for line in report.split("\n"):
                print(f"{line}\033[K")
            
            # Add a footer
            print(f"\n[Ctrl+C to Exit] | Refreshing every 2 seconds...\033[K")
            
            time.sleep(2)
    except KeyboardInterrupt:
        # Show cursor again on exit
        print("\033[?25h")
        print("\nExiting Glass Cockpit...")
        sys.exit(0)

if __name__ == "__main__":
    run_live_dashboard()
