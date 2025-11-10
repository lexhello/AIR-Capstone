from bleak import BleakScanner
import asyncio

async def scan():
    devices = await BleakScanner.discover(timeout=8.0)
    for d in devices:
        print(d)

asyncio.run(scan())