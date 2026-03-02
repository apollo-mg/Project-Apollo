import asyncio
from kasa import Discover
import pychromecast
import json

async def discover_kasa():
    print("Discovering Kasa devices...")
    found_devices = await Discover.discover()
    kasa_list = []
    for ip, dev in found_devices.items():
        await dev.update()
        kasa_list.append({
            "ip": ip,
            "alias": dev.alias,
            "model": dev.model,
            "is_on": dev.is_on
        })
    return kasa_list

def discover_cast():
    print("Discovering Cast devices...")
    chromecasts, browser = pychromecast.get_chromecasts()
    cast_list = []
    for cc in chromecasts:
        cast_list.append({
            "ip": cc.host,
            "name": cc.name,
            "model_name": cc.model_name,
            "uuid": str(cc.uuid)
        })
    pychromecast.discovery.stop_discovery(browser)
    return cast_list

async def main():
    kasa_devs = await discover_kasa()
    cast_devs = discover_cast()
    
    report = {
        "kasa": kasa_devs,
        "cast": cast_devs
    }
    print(json.dumps(report, indent=2))

if __name__ == "__main__":
    asyncio.run(main())
