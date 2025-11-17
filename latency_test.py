import asyncio
import time
from bleak import BleakScanner, BleakClient

SERVICE_UUID = "12345678-1234-1234-1234-1234567890ab"
CHAR_UUID    = "abcdefab-1234-5678-90ab-abcdefabcdef"


async def main():
    print("Scanning...")
    devices = await BleakScanner.discover()

    target = None
    for d in devices:
        if d.name and "XIAO_ESP32S3" in d.name:
            target = d
            break

    if not target:
        print("ESP32 not found.")
        return

    print("Connecting to:", target.address)

    async with BleakClient(target.address) as client:
        await client.start_notify(CHAR_UUID, notification_handler)

        print("Connected. Starting latency test...\n")

        for i in range(20):  # send 20 test packets
            send_time = time.time_ns()
            msg = str(send_time).encode()

            await client.write_gatt_char(CHAR_UUID, msg)

            # Wait for echo
            ts = await wait_queue.get()

            rtt_ms = (time.time_ns() - ts) / 1e6
            print(f"{i:02d} | Round-trip: {rtt_ms:.3f} ms")

        print("\nDone.")
        await client.stop_notify(CHAR_UUID)


# queue for notifications
class SimpleQueue:
    def __init__(self):
        self.fut = None

    async def get(self):
        self.fut = asyncio.get_event_loop().create_future()
        return await self.fut

    def set(self, value):
        if self.fut and not self.fut.done():
            self.fut.set_result(value)

wait_queue = SimpleQueue()


def notification_handler(sender, data: bytearray):
    try:
        ts = int(data.decode())
        wait_queue.set(ts)
    except Exception:
        pass


asyncio.run(main())

