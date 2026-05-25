import asyncio
import sys
import difflib
from kasa import Discover

async def control_device(target_name, action):
    # normalize target
    target_clean = target_name.lower().strip()
    
    # 1. Discover devices (fast discovery)
    found_devices = await Discover.discover(timeout=2)
    
    target_dev = None
    
    # 2. Exact/Substring Match
    for ip, dev in found_devices.items():
        alias_clean = dev.alias.lower().strip()
        if target_clean == alias_clean:
            target_dev = dev
            break
        if target_clean in alias_clean or alias_clean in target_clean:
             # Prefer exact substring matches, but keep checking for exact
             if target_dev is None: target_dev = dev
            
    # 3. Fuzzy Match (if no exact/substring)
    if not target_dev:
        aliases = {dev.alias.lower(): dev for dev in found_devices.values()}
        matches = difflib.get_close_matches(target_clean, aliases.keys(), n=1, cutoff=0.4)
        if matches:
            best_alias = matches[0]
            target_dev = aliases[best_alias]
            print(f"Did you mean '{target_dev.alias}'? Executing...")

    if not target_dev:
        print(f"Error: Device '{target_name}' not found.")
        # Print available for debugging
        print("Available: " + ", ".join([d.alias for d in found_devices.values()]))
        return

    # 4. Perform Action
    await target_dev.update()
    
    if action == "on":
        await target_dev.turn_on()
        print(f"Turned ON: {target_dev.alias}")
    elif action == "off":
        await target_dev.turn_off()
        print(f"Turned OFF: {target_dev.alias}")
    elif action == "toggle":
        if target_dev.is_on:
            await target_dev.turn_off()
            print(f"Toggled OFF: {target_dev.alias}")
        else:
            await target_dev.turn_on()
            print(f"Toggled ON: {target_dev.alias}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python kasa_control.py <name> <on/off/toggle> OR python kasa_control.py list")
        sys.exit(1)
        
    if sys.argv[1] == "list":
        async def list_devices():
            print("Discovering devices...")
            devs = await Discover.discover(timeout=3)
            if not devs:
                print("No devices found.")
            for ip, dev in devs.items():
                print(f" - {dev.alias} ({ip})")
        asyncio.run(list_devices())
        sys.exit(0)

    if len(sys.argv) < 3:
        print("Usage: python kasa_control.py <name> <on/off/toggle>")
        sys.exit(1)

    name_arg = sys.argv[1]
    action_arg = sys.argv[2].lower()
    
    try:
        asyncio.run(control_device(name_arg, action_arg))
    except Exception as e:
        print(f"Error: {e}")
